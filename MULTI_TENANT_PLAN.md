# Piano: Multi-Tenant Isolation con Auth + Dati Isolati

## Contesto

Attualmente il backend Elysia non ha autenticazione: il `user_id` è inviato dal client senza validazione, e tutte le collezioni Weaviate sono visibili a tutti. L'obiettivo è:
- **Validare il JWT Supabase** nel backend (offline con JWT_SECRET condiviso)
- **Isolare l'accesso alle collezioni** per organizzazione (da `companyName` nel token LDAP)
- **Default**: tutti hanno accesso a `UNIInternalDocs`
- Le conversazioni restano legate a `user_id`

## Step 1: Schema Supabase — Tabelle organizzazioni e mapping

**File**: `supabase-project/dev/data.sql`

Aggiungere:

```sql
-- Tabella organizzazioni
create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text unique not null,       -- corrisponde a companyName dal token LDAP
  created_at timestamptz default now()
);

-- Mapping org → collezioni Weaviate permesse
create table organization_collections (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid references organizations(id) on delete cascade,
  collection_name text not null,
  unique(organization_id, collection_name)
);

-- Aggiungere organization_id a profiles
alter table profiles add column organization_id uuid references organizations(id);

-- RLS
alter table organizations enable row level security;
alter table organization_collections enable row level security;

-- Tutti possono leggere le org (serve al backend per il mapping)
create policy "Organizations are viewable by authenticated users"
  on organizations for select using (auth.role() = 'authenticated');

create policy "Org collections are viewable by authenticated users"
  on organization_collections for select using (auth.role() = 'authenticated');

-- Seed: organizzazione default + accesso a UNIInternalDocs
insert into organizations (name) values ('UNI');
insert into organization_collections (organization_id, collection_name)
  select id, 'UNIInternalDocs' from organizations where name = 'UNI';
```

## Step 2: Propagare companyName dall'LDAP token a Supabase user metadata

**Problema**: Supabase GoTrue (provider Azure) chiama il userinfo endpoint del ldap-emulator e mappa i claim nel profilo utente. Il `companyName` è già restituito dal userinfo endpoint (`ldap-emulator/routers/oidc.py:116`), ma GoTrue non lo estrae automaticamente in `app_metadata`.

**Soluzione**: Usare un **Database Webhook / Trigger** su Supabase che, al primo login (insert su `auth.users`), legge il `raw_user_meta_data` e popola `organization_id` nella tabella `profiles`.

**File**: `supabase-project/dev/data.sql` (aggiungere)

```sql
-- Trigger: al primo login, associa utente all'organizzazione basata su companyName
create or replace function handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, username, organization_id)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'preferred_username', new.email),
    (select id from public.organizations
     where name = coalesce(new.raw_user_meta_data->>'companyName', 'UNI')
     limit 1)
  )
  on conflict (id) do update set
    organization_id = coalesce(
      (select id from public.organizations
       where name = coalesce(new.raw_user_meta_data->>'companyName', 'UNI')
       limit 1),
      profiles.organization_id
    );
  return new;
end;
$$ language plpgsql security definer;

-- Connettere trigger ad auth.users
create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_user();
```

**Verifica necessaria**: controllare che GoTrue Azure provider salvi effettivamente `companyName` nel `raw_user_meta_data`. Se non lo fa, aggiungere il claim nelle `scopes` richieste o mapparlo nel ldap-emulator come claim standard.

## Step 3: Backend Elysia — Middleware JWT validation

**Nuovo file**: `elysia/elysia/api/middleware/auth.py`

```python
import jwt
import os
from fastapi import Request, WebSocket, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
PUBLIC_PATHS = {"/api/health", "/docs", "/openapi.json"}

class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            raise HTTPException(status_code=401, detail="Missing token")

        try:
            payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")
            request.state.user_id = payload["sub"]
            request.state.jwt_payload = payload
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

        return await call_next(request)
```

**Per WebSocket** (non supporta middleware HTTP standard): validare il token nel primo messaggio o come query parameter.

**File da modificare**: `elysia/elysia/api/app.py` — registrare il middleware
**File da modificare**: `elysia/.env.example` — aggiungere `SUPABASE_JWT_SECRET`

## Step 4: Backend — Filtrare collezioni per organizzazione

**File**: `elysia/elysia/api/routes/collections.py` (riga 109-115)

Cambiare il listing delle collezioni per filtrare in base all'org dell'utente:

1. Dal JWT estrarre `user_id` (sub)
2. Chiamare Supabase (o cache locale) per ottenere `organization_id` del profilo
3. Query `organization_collections` per ottenere le collezioni permesse
4. Filtrare `client.collections.list_all()` con le collezioni permesse

**Approccio concreto**: aggiungere un servizio `AuthService` nel backend che:
- Valida JWT e ritorna user_id
- Mantiene una cache `user_id → allowed_collections` (con TTL)
- Espone `get_allowed_collections(user_id) → list[str]`

**Nuovo file**: `elysia/elysia/api/services/auth.py`

Questo servizio fa query a Supabase via PostgREST o connessione diretta PostgreSQL per ottenere il mapping. In sviluppo locale può usare `http://localhost:8000/rest/v1/` con la service role key.

## Step 5: Backend — Filtrare collezioni nella query WebSocket

**File**: `elysia/elysia/api/routes/query.py` (riga 98-105)

Le `collection_names` inviate dal frontend devono essere intersecate con le collezioni permesse all'utente. Se il frontend chiede una collezione non autorizzata → ignorarla silenziosamente o restituire errore.

```python
allowed = await auth_service.get_allowed_collections(user_id)
requested = data["collection_names"]
authorized = [c for c in requested if c in allowed]
```

## Step 6: Frontend — Inviare il JWT token al backend

**File**: `elysia-frontend/app/components/contexts/SocketContext.tsx`

Aggiungere il token Supabase ai messaggi WebSocket o come query param nella connessione:

```typescript
// Ottenere il token dalla sessione Supabase
const { data: { session } } = await supabase.auth.getSession();
const token = session?.access_token;

// Opzione A: query param nella URL WebSocket
const ws = new WebSocket(`ws://host:8090/ws/query?token=${token}`);

// Opzione B: primo messaggio / header in ogni messaggio
socket.send(JSON.stringify({ ...payload, token }));
```

**File**: `elysia-frontend/hooks/useAuthUserId.ts` o context appropriato — esporre il token

Per le chiamate REST (`/init/user`, `/collections`, ecc.), aggiungere `Authorization: Bearer <token>` header.

## Step 7: Dati di test

**File**: `ldap-emulator/data/users.json` — verificare che tutti gli utenti test abbiano `companyName: "UNI"`

**File**: `supabase-project/dev/data.sql` — i seed inseriscono già l'org "UNI" con accesso a "UNIInternalDocs"

## Ordine di implementazione consigliato

1. Step 1+2: Schema Supabase + trigger (indipendente dal resto)
2. Step 3: Middleware JWT nel backend (può essere testato subito)
3. Step 6: Frontend invia token (necessario per step 3)
4. Step 4+5: Filtraggio collezioni (la parte centrale)
5. Step 7: Verifica end-to-end

## File da modificare (riepilogo)

| File | Modifica |
|------|----------|
| `supabase-project/dev/data.sql` | Nuove tabelle, trigger, seed |
| `elysia/elysia/api/middleware/auth.py` | **Nuovo** — JWT middleware |
| `elysia/elysia/api/services/auth.py` | **Nuovo** — AuthService per mapping org→collections |
| `elysia/elysia/api/app.py` | Registrare middleware auth |
| `elysia/elysia/api/routes/collections.py` | Filtrare collezioni per org |
| `elysia/elysia/api/routes/query.py` | Validare token WS, filtrare collection_names |
| `elysia/elysia/api/routes/init.py` | Validare token su init |
| `elysia/.env.example` | Aggiungere `SUPABASE_JWT_SECRET` |
| `elysia-frontend/.../SocketContext.tsx` | Inviare JWT al backend |
| `elysia-frontend/` (chiamate REST) | Aggiungere Authorization header |

## Verifica

1. Login con `demo@uni.local` → verificare che `profiles.organization_id` sia popolato
2. Chiamare `/collections` senza token → 401
3. Chiamare `/collections` con token → solo `UNIInternalDocs` (e altre collezioni assegnate a UNI)
4. WebSocket query su collezione non autorizzata → rifiutata
5. Creare un utente con `companyName` diverso → non vede `UNIInternalDocs` (a meno che la sua org non sia configurata)
