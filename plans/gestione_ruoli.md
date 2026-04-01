# PRD: Gestione Autorizzazioni Basata sui Ruoli (RBAC)

**Stato:** Draft  
**Data:** 2026-04-01  
**Autore:** Leonardo Porcacchia  

---

## 1. Contesto

Atena attualmente ha un campo `app_role` (testo singolo, default `'user'`) nella tabella `user_profiles` di Supabase. Questo campo non supporta ruoli multipli per utente e non e' collegato a nessuna logica di autorizzazione applicativa.

Serve un sistema RBAC molti-a-molti che permetta di assegnare piu' ruoli a ciascun utente, gestibili da Supabase Studio e visibili (read-only) nel frontend.

### Stato attuale di `app_role` nella codebase

Il campo `app_role` e' presente nei seguenti punti e va **rimosso completamente** con questa implementazione:

| File | Riga | Cosa fa | Azione richiesta |
|------|------|---------|------------------|
| `supabase-project/volumes/db/athena_schema.sql` | 33 | Definizione colonna `app_role text NOT NULL DEFAULT 'user'` | Rimuovere colonna dalla CREATE TABLE |
| `supabase-project/volumes/db/athena_schema.sql` | 100 | Trigger `handle_new_user()` inserisce `app_role` nel profilo | Rimuovere `app_role` dalla INSERT del trigger |
| `elysia-frontend/scripts/auth-config/profile-schema.sql` | 48 | Schema duplicato: stessa definizione colonna | Rimuovere colonna dalla CREATE TABLE |
| `elysia-frontend/hooks/useUserProfile.ts` | 50 | Default `app_role: "user"` nel profilo creato client-side | Rimuovere il campo dal default profile |
| `elysia-frontend/app/types/profile-types.ts` | 33 | Tipo TypeScript `app_role: string` | Rimuovere il campo dall'interfaccia |
| Backend elysia (`elysia/`) | — | Nessun riferimento | Nessuna azione |

> **Nota:** nessuna logica applicativa dipende da `app_role` per decisioni di autorizzazione. La rimozione e' sicura.

## 2. Obiettivo

Implementare una gestione delle autorizzazioni basata sui ruoli con le seguenti caratteristiche:
- Relazione molti-a-molti tra utenti e ruoli
- Gestione ruoli esclusivamente via Supabase Studio (da parte degli ADMIN)
- Visualizzazione read-only dei ruoli nella pagina Profile del frontend
- Ruoli trasmessi al backend durante il login come array di stringhe

## 3. Schema Dati

### 3.1 Nuova tabella: `roles`

Catalogo dei ruoli disponibili nel sistema.

```sql
CREATE TABLE public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,          -- es. 'ADMIN', 'THOTH', 'NORME', 'GRAPHIC', 'USER'
    description TEXT,                    -- descrizione opzionale del ruolo
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.2 Nuova tabella ponte: `user_roles`

Relazione molti-a-molti tra `user_profiles` e `roles`. La FK punta a `user_profiles.id` (non direttamente ad `auth.users`), mantenendo `user_profiles` come unica tabella di riferimento per l'identita' utente nel dominio applicativo.

```sql
CREATE TABLE public.user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.user_profiles(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, role_id)           -- un utente non puo' avere lo stesso ruolo due volte
);

CREATE INDEX idx_user_roles_user_id ON public.user_roles(user_id);
```

### 3.3 Ruoli predefiniti (seed data)

| Nome      | Descrizione |
|-----------|-------------|
| `ADMIN`   | Amministratore di sistema con accesso completo |
| `THOTH`   | Accesso alle funzionalita' ThothAI |
| `NORME`   | Accesso ai contenuti normativi |
| `GRAPHIC` | Accesso agli strumenti di grafica |
| `USER`    | Ruolo base assegnato a tutti gli utenti |

### 3.4 Assegnazione ruoli iniziale

**Ogni utente esistente** riceve il ruolo `USER` (via migration).

**Ruolo ADMIN** assegnato anche a:
- `leonardo.porcacchia@uni.com`
- `simone.mezzabotta@uni.com`
- `marco.pancotti@ext_uni.com`
- `sofia.zanrosso@uni.com`
- `lisa.inversini@uni.com`
- `domenico.falvella@uni.com`
- `paolo.sanna@uni.com`

> **Nota:** il match va fatto tramite JOIN `auth.users.email` → `auth.users.id` = `user_profiles.id`, dato che `user_profiles.id` referenzia `auth.users(id)`. La relazione `user_roles` punta a `user_profiles.id`.

```sql
-- Esempio seed ADMIN
INSERT INTO public.user_roles (user_id, role_id)
SELECT up.id, r.id
FROM auth.users au
JOIN public.user_profiles up ON up.id = au.id
CROSS JOIN public.roles r
WHERE r.name = 'ADMIN'
  AND au.email IN (
    'leonardo.porcacchia@uni.com',
    'simone.mezzabotta@uni.com',
    'marco.pancotti@ext_uni.com',
    'sofia.zanrosso@uni.com',
    'lisa.inversini@uni.com',
    'domenico.falvella@uni.com',
    'paolo.sanna@uni.com'
  )
ON CONFLICT (user_id, role_id) DO NOTHING;
```

### 3.5 Trigger: assegnazione automatica ruolo USER

Ogni nuovo utente che si registra riceve automaticamente il ruolo `USER`.

```sql
CREATE OR REPLACE FUNCTION public.assign_default_role()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_roles (user_id, role_id)
    SELECT NEW.id, r.id FROM public.roles r WHERE r.name = 'USER';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_user_profile_created_assign_role
    AFTER INSERT ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.assign_default_role();
```

### 3.6 RLS (Row Level Security)

```sql
-- roles: leggibile da tutti gli utenti autenticati
ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can read roles" ON public.roles
    FOR SELECT TO authenticated USING (true);

-- user_roles: ogni utente vede solo i propri ruoli
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own roles" ON public.user_roles
    FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- service_role ha accesso completo (per Supabase Studio e migration)
CREATE POLICY "Service role full access roles" ON public.roles
    FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access user_roles" ON public.user_roles
    FOR ALL TO service_role USING (true) WITH CHECK (true);
```

### 3.7 Rimozione del campo `app_role`

Il campo `user_profiles.app_role` viene **eliminato** in questa iterazione. La migration deve:

1. **Eliminare la colonna** da `user_profiles`:
   ```sql
   ALTER TABLE public.user_profiles DROP COLUMN app_role;
   ```

2. **Aggiornare il trigger `handle_new_user()`** rimuovendo `app_role` dalla INSERT (il nuovo trigger `assign_default_role` della sezione 3.5 si occupa di assegnare il ruolo `USER` via `user_roles`):
   ```sql
   CREATE OR REPLACE FUNCTION public.handle_new_user()
   RETURNS trigger AS $$
   BEGIN
       INSERT INTO public.user_profiles (id, display_name)
       VALUES (
           NEW.id,
           COALESCE(NEW.raw_user_meta_data->>'Display Name', NEW.raw_user_meta_data->>'full_name', '')
       );
       RETURN NEW;
   END;
   $$ LANGUAGE plpgsql SECURITY DEFINER;
   ```

3. **Aggiornare i file frontend** (vedi tabella nella sezione 1 per la lista completa):
   - Rimuovere `app_role` dal tipo `UserProfile` in `profile-types.ts`
   - Rimuovere `app_role` dal default profile in `useUserProfile.ts`
   - Rimuovere `app_role` dallo schema in `profile-schema.sql`

## 4. Modifiche Frontend

### 4.1 Fetch ruoli utente

**File:** `elysia-frontend/hooks/useUserProfile.ts`

Dopo il fetch del profilo, eseguire una query aggiuntiva:

```ts
const { data: userRoles } = await supabase
    .from('user_roles')
    .select('roles(name)')
    .eq('user_id', userId);
```

Esporre i ruoli come `string[]` (es. `['USER', 'ADMIN']`) nel return del hook.

### 4.2 Tipo `UserProfile`

**File:** `elysia-frontend/app/types/profile-types.ts`

- Rimuovere il campo `app_role: string`
- Aggiungere il campo `roles: string[]` all'interfaccia `UserProfile`

### 4.3 Pagina Profile (read-only)

**File:** `elysia-frontend/app/pages/ProfilePage.tsx`

Aggiungere una sezione "Ruoli" nella card dell'identita' organizzativa, che mostra i ruoli come badge/chip read-only. Nessun controllo di modifica.

### 4.4 Trasmissione ruoli al backend

I ruoli devono essere inclusi nella chiamata di inizializzazione verso Elysia (`/init/user/{user_id}`) o in una chiamata dedicata post-login, come array di stringhe nel payload:

```json
{
    "user_id": "uuid",
    "roles": ["USER", "ADMIN"],
    "job_title": "...",
    "department": "..."
}
```

## 5. Modifiche Backend (Elysia)

### 5.1 Ricezione ruoli

**File:** `elysia/api/routes/init.py`

L'endpoint `POST /init/user/{user_id}` deve accettare un campo opzionale `roles: list[str]` nel body e salvarlo nello stato utente in-memory (`UserManager`).

### 5.2 Persistenza in-memory

**File:** `elysia/api/services/user.py`

`UserManager` deve memorizzare i ruoli dell'utente per renderli disponibili durante la sessione. Non serve persistenza lato backend (la source of truth e' Supabase).

## 6. Test

### 6.1 Unit test Supabase (SQL)

- Verificare che la creazione di un `user_profile` scateni l'assegnazione automatica del ruolo `USER`
- Verificare il vincolo di unicita' `(user_id, role_id)`
- Verificare che RLS impedisca a un utente di leggere i ruoli di un altro utente

### 6.2 Unit test Frontend

- Mock del fetch ruoli: verificare che `useUserProfile` restituisca `roles: string[]`
- Verificare che la pagina Profile mostri i ruoli come read-only
- Verificare che i ruoli vengano inclusi nel payload di init verso il backend

### 6.3 Unit test Backend (Elysia)

**Da aggiungere in:** `tests/no_reqs/api/`

- Verificare che `POST /init/user/{user_id}` accetti e memorizzi i ruoli
- Verificare che un utente senza ruoli espliciti riceva un default vuoto o `['USER']`
- Verificare che i ruoli siano accessibili dal `UserManager` dopo l'init

## 7. Fuori Scope (per ora)

- **Enforcement delle autorizzazioni**: questa PRD copre solo la struttura dati e il trasporto dei ruoli. La logica "il ruolo X puo' fare Y" sara' oggetto di una PRD separata
- **UI di gestione ruoli**: la gestione avviene esclusivamente via Supabase Studio
- **Audit log** delle modifiche ai ruoli

## 8. Piano di Implementazione (ordine suggerito)

| Step | Cosa | Dove | Dipendenze |
|------|------|------|------------|
| 1 | Migration SQL: tabelle `roles`, `user_roles`, seed ruoli, trigger auto-assign, RLS | `supabase-project/` | Nessuna |
| 2 | Seed ruolo USER a tutti gli utenti esistenti + ADMIN per utenti iniziali | `supabase-project/` | Step 1 |
| 3 | Rimozione colonna `app_role` da `user_profiles` + aggiornamento trigger `handle_new_user()` | `supabase-project/` | Step 1, 2 |
| 4 | Rimozione `app_role` da tipi, hook e schema frontend | `elysia-frontend/` | Step 3 |
| 5 | Hook `useUserProfile`: fetch ruoli da `user_roles` + esporre come `roles: string[]` | `elysia-frontend/` | Step 1, 4 |
| 6 | Pagina Profile: sezione ruoli read-only | `elysia-frontend/` | Step 5 |
| 7 | Payload init: includere ruoli nella chiamata a Elysia | `elysia-frontend/` | Step 5 |
| 8 | Endpoint init: accettare e memorizzare ruoli | `elysia/` | Step 7 |
| 9 | Test SQL, frontend, backend | Tutti | Step 1-8 |

## 9. Rischi e Mitigazioni

| Rischio | Mitigazione |
|---------|-------------|
| Match email per seed ADMIN fallisce (email diverse in `auth.users`) | Verificare le email esatte in `auth.users` prima di eseguire la migration. La query usa `ON CONFLICT DO NOTHING` per essere idempotente |
| Rimozione `app_role` rompe codice non individuato | Analisi completata: `app_role` non e' usato in nessuna logica applicativa nel backend. Nel frontend e' solo nel tipo e nel default profile — entrambi coperti dal piano. Nessun rischio residuo |
| Performance: query aggiuntiva per ruoli a ogni caricamento profilo | Impatto trascurabile: join su tabella piccola con indice su `user_id`. Valutare caching se necessario |
