# Piano: ThothAI su hostname separato

## Context

ThothAI gira sullo stesso host di Athena (`10.1.1.11`) su una porta diversa (8040 vs 3090). I cookie HTTP non supportano scoping per porta: il browser invia tutti i cookie di `10.1.1.11` a qualsiasi servizio su quell'IP, incluso il JWT Supabase (~1KB+ per chunk, multipli chunk). Questo causa "400 Bad Request — Request Header Or Cookie Too Large" quando si apre ThothAI.

**Workaround attuale** (nel codice): rimozione temporanea dei cookie prima di aprire il popup ThothAI. Funziona ma è fragile (finestra di 500ms senza cookie).

**Soluzione definitiva**: far girare ThothAI su un hostname diverso così che i cookie Supabase non vengano inviati.

## Architettura attuale

```
10.1.1.11:3090  → elysia-frontend (Next.js)
10.1.1.11:8090  → elysia backend (FastAPI)
10.1.1.11:8000  → Supabase Kong
10.1.1.11:8040  → thoth-proxy (Nginx → thoth-backend + thoth-frontend)
10.1.1.11:3040  → thoth-frontend (diretto)
10.1.1.11:8020  → thoth-sql-generator
```

Tutti sullo stesso IP → stesso cookie jar → problema.

## Stack ThothAI

Definito in: `/opt/athena/supabase-project/docker-compose.thoth.yml`

| Servizio | Porta interna | Porta esposta |
|----------|--------------|---------------|
| thoth-proxy (Nginx) | 80 | **8040** |
| thoth-frontend (Next.js) | 3000 | 3040 |
| thoth-backend (Django) | 8000 | — |
| thoth-sql-generator (FastAPI) | 8001 | 8020 |
| thoth-qdrant | 6333 | 6333 |
| thoth-mermaid-service | — | 8003 |

## Soluzione proposta: hostname via /etc/hosts

L'approccio più semplice che non richiede DNS esterno: aggiungere un hostname locale in `/etc/hosts` e configurare ThothAI per rispondere a quel nome.

### Step 1: Aggiungere entry in /etc/hosts

```bash
# Su tutte le macchine che accedono ad Athena (server + client)
echo "10.1.1.11 thoth.athena.local" | sudo tee -a /etc/hosts
```

Per i client (browser degli utenti), questa entry va aggiunta nella macchina da cui navigano, oppure si può usare un DNS interno se disponibile.

### Step 2: Configurare ThothAI per il nuovo hostname

File: `/opt/athena/supabase-project/thoth-config/.env.thoth`

```diff
- THOTH_PUBLIC_HOST=10.1.1.11
+ THOTH_PUBLIC_HOST=thoth.athena.local
- SERVER_NAME=localhost
+ SERVER_NAME=thoth.athena.local
- ALLOWED_HOSTS=thoth-proxy,thoth-backend,10.1.1.11
+ ALLOWED_HOSTS=thoth-proxy,thoth-backend,10.1.1.11,thoth.athena.local
```

### Step 3: Aggiornare il frontend Athena

File: `/opt/athena/elysia-frontend/.env.local`

```diff
- NEXT_PUBLIC_THOTH_URL=http://10.1.1.11:8040
+ NEXT_PUBLIC_THOTH_URL=http://thoth.athena.local:8040
```

### Step 4: Aggiornare CORS/origin in ThothAI

File: `/opt/athena/supabase-project/thoth-config/.env.thoth`

Verificare che `RUNTIME_ATHENA_ORIGIN` sia corretto:
```
RUNTIME_ATHENA_ORIGIN=http://10.1.1.11:8090
```

ThothAI deve accettare postMessage da Athena, quindi l'origin di Athena deve restare quello attuale.

### Step 5: Rimuovere il workaround cookie dal frontend

File: `/opt/athena/elysia-frontend/app/components/navigation/SidebarComponent.tsx`

Rimuovere tutta la logica di salvataggio/rimozione/ripristino cookie e tornare al semplice `window.open`:

```typescript
popup = window.open(
  `${thothUrl}/auth/supabase?athena_origin=${encodeURIComponent(window.location.origin)}`,
  '_blank'
);
```

### Step 6: Restart dei servizi

```bash
# Ricostruire ThothAI con il nuovo hostname
cd /opt/athena/supabase-project
docker compose -f docker-compose.thoth.yml down
docker compose -f docker-compose.thoth.yml up -d

# Ricostruire il frontend
cd /opt/athena/elysia-frontend
npm run assemble
# Oppure npm run dev se in dev mode
```

## File da modificare (riepilogo)

| File | Modifica |
|------|----------|
| `/etc/hosts` (server) | Aggiungere `10.1.1.11 thoth.athena.local` |
| `/etc/hosts` (client) | Aggiungere `10.1.1.11 thoth.athena.local` (o DNS interno) |
| `supabase-project/thoth-config/.env.thoth` | `THOTH_PUBLIC_HOST`, `SERVER_NAME`, `ALLOWED_HOSTS` |
| `elysia-frontend/.env.local` | `NEXT_PUBLIC_THOTH_URL` |
| `elysia-frontend/app/components/navigation/SidebarComponent.tsx` | Rimuovere workaround cookie |

## Alternativa: DNS interno (se disponibile)

Se c'è un DNS interno aziendale, si può creare un record A:
```
thoth.athena.company.com → 10.1.1.11
```

Questo elimina la necessità di modificare `/etc/hosts` su ogni client.

## Alternativa avanzata: reverse proxy unico

Installare un reverse proxy (Nginx/Caddy) sull'host che faccia routing basato su hostname:

```
athena.local:80     → elysia-frontend:3090
thoth.athena.local:80 → thoth-proxy:8040
```

Questo eliminerebbe anche la necessità di specificare le porte negli URL, ma richiede più configurazione e non è strettamente necessario per risolvere il problema cookie.

## Verifica

1. Aprire Athena nel browser → login
2. Cliccare "ThothAI" nella sidebar
3. Il popup si apre su `http://thoth.athena.local:8040/...` senza errore 400
4. L'autenticazione via postMessage funziona normalmente
5. I cookie Supabase NON vengono inviati a ThothAI (hostname diverso = cookie jar diverso)
