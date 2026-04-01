# Gestione Ruoli (RBAC)

Atena implementa un sistema di autorizzazione basato sui ruoli (RBAC) con relazione molti-a-molti tra utenti e ruoli. I ruoli vengono gestiti esclusivamente via Supabase Studio e sono visibili in sola lettura nella pagina Profilo del frontend.

## Schema Dati

### Tabella `roles`

Catalogo dei ruoli disponibili nel sistema.

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `id` | UUID (PK) | Identificativo univoco |
| `name` | TEXT (UNIQUE) | Nome del ruolo (es. `ADMIN`, `USER`) |
| `description` | TEXT | Descrizione opzionale |
| `created_at` | TIMESTAMPTZ | Data di creazione |

### Tabella `user_roles`

Tabella ponte tra `user_profiles` e `roles`.

| Colonna | Tipo | Descrizione |
|---------|------|-------------|
| `id` | UUID (PK) | Identificativo univoco |
| `user_id` | UUID (FK -> `user_profiles.id`) | Riferimento all'utente |
| `role_id` | UUID (FK -> `roles.id`) | Riferimento al ruolo |
| `assigned_at` | TIMESTAMPTZ | Data di assegnazione |

Vincolo: `UNIQUE (user_id, role_id)` — un utente non puo' avere lo stesso ruolo due volte.

### Relazione con le altre tabelle

```
auth.users (Supabase Auth)
    |
    | id (UUID)
    v
user_profiles
    |
    | id (UUID, FK -> auth.users.id)
    v
user_roles (junction)
    |
    | user_id (FK -> user_profiles.id)
    | role_id (FK -> roles.id)
    v
roles (catalog)
```

La FK di `user_roles` punta a `user_profiles.id`, non direttamente ad `auth.users`. Questo mantiene `user_profiles` come unica tabella di riferimento per l'identita' utente nel dominio applicativo.

## Ruoli Predefiniti

| Nome | Descrizione |
|------|-------------|
| `ADMIN` | Amministratore di sistema con accesso completo |
| `THOTH` | Accesso alle funzionalita' ThothAI |
| `NORME` | Accesso ai contenuti normativi |
| `GRAPHIC` | Accesso agli strumenti di grafica |
| `USER` | Ruolo base assegnato a tutti gli utenti |

## Comportamento Automatico

### Assegnazione ruolo USER

Ogni nuovo utente riceve automaticamente il ruolo `USER` tramite il trigger `on_user_profile_created_assign_role`, che si attiva dopo l'inserimento di un record in `user_profiles`.

### Row Level Security (RLS)

| Tabella | Policy | Chi | Cosa |
|---------|--------|-----|------|
| `roles` | `roles_select_authenticated` | Utenti autenticati | Lettura di tutti i ruoli |
| `roles` | `roles_service_role_all` | service_role | Accesso completo |
| `user_roles` | `user_roles_select_own` | Utenti autenticati | Lettura dei propri ruoli (`auth.uid() = user_id`) |
| `user_roles` | `user_roles_service_role_all` | service_role | Accesso completo |

## Gestione Ruoli (Supabase Studio)

I ruoli vengono gestiti esclusivamente tramite Supabase Studio. Non esiste una UI di gestione nel frontend.

### Assegnare un ruolo a un utente

1. Aprire Supabase Studio (porta 8000, path `/project/default/editor`)
2. Navigare alla tabella `user_roles`
3. Inserire un nuovo record con:
   - `user_id`: l'UUID dell'utente (reperibile da `user_profiles`)
   - `role_id`: l'UUID del ruolo (reperibile da `roles`)
4. Il vincolo di unicita' impedisce assegnazioni duplicate

### Revocare un ruolo

Eliminare il record corrispondente dalla tabella `user_roles`.

### Creare un nuovo ruolo

Inserire un record nella tabella `roles` con `name` (univoco) e `description` opzionale.

## Flusso nel Frontend

### Caricamento profilo

L'hook `useUserProfile` (`hooks/useUserProfile.ts`) esegue una query sulla tabella `user_roles` con join su `roles` per ottenere i nomi dei ruoli dell'utente:

```ts
const { data: rolesData } = await supabase
    .from("user_roles")
    .select("roles(name)")
    .eq("user_id", userId);
```

I ruoli vengono esposti come `string[]` (es. `["USER", "ADMIN"]`) nel campo `roles` dell'interfaccia `UserProfile`.

### Pagina Profilo

I ruoli sono visualizzati nella sezione "Identita' Organizzativa" della pagina Profilo come badge read-only. L'utente non puo' modificarli.

### Trasmissione al Backend

Durante l'inizializzazione utente, `SessionContext` recupera i ruoli da Supabase e li passa al backend Elysia tramite il body della POST a `/init/user/{user_id}`:

```json
{
    "roles": ["USER", "ADMIN"]
}
```

## Flusso nel Backend (Elysia)

### Ricezione ruoli

L'endpoint `POST /init/user/{user_id}` accetta un body opzionale di tipo `InitialiseUserData`:

```python
class InitialiseUserData(BaseModel):
    roles: list[str] = []
```

Se il body non viene fornito, i ruoli sono impostati a lista vuota.

### Persistenza in-memory

I ruoli vengono salvati nel dizionario utente del `UserManager`:

```python
user_manager.users[user_id]["roles"]  # list[str]
```

La source of truth resta Supabase. Il backend conserva i ruoli solo in memoria per la durata della sessione.

### Accesso ai ruoli

Per leggere i ruoli di un utente nel backend:

```python
roles = user_manager.users[user_id].get("roles", [])
```

## File Coinvolti

| File | Cosa contiene |
|------|--------------|
| `supabase-project/volumes/db/athena_schema.sql` | Definizione tabelle, RLS, trigger, seed |
| `elysia-frontend/app/types/profile-types.ts` | Interfaccia `UserProfile` con campo `roles: string[]` |
| `elysia-frontend/hooks/useUserProfile.ts` | Query ruoli da `user_roles` |
| `elysia-frontend/app/pages/ProfilePage.tsx` | Visualizzazione badge ruoli |
| `elysia-frontend/app/api/initializeUser.ts` | Invio ruoli al backend |
| `elysia-frontend/app/components/contexts/SessionContext.tsx` | Fetch ruoli e passaggio a `initializeUser` |
| `elysia/elysia/api/api_types.py` | Modello `InitialiseUserData` |
| `elysia/elysia/api/routes/init.py` | Endpoint `/init/user` con supporto ruoli |
| `elysia/elysia/api/services/user.py` | Memorizzazione ruoli in `UserManager` |
