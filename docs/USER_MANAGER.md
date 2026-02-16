# UserManager - Documentazione Tecnica

## Panoramica

`UserManager` (`elysia/api/services/user.py`) è il **gestore centralizzato di sessioni utente** nel backend Elysia. È implementato come singleton che mantiene in memoria lo stato per ogni utente connesso, isolando le loro conversazioni, configurazioni e connessioni Weaviate.

## Architettura

### Struttura Dati Principale

```python
UserManager.users = {
    "user_id_1": {
        "tree_manager": TreeManager,      # Gestisce le conversazioni (Tree)
        "client_manager": ClientManager,  # Gestisce connessioni Weaviate
        "frontend_config": FrontendConfig, # Preferenze UI + save location
        "last_request": datetime           # Timestamp per timeout tracking
    },
    "user_id_2": {
        ...
    }
}
```

**Nota critica**: La chiave `user_id` è **inviata dal client senza validazione**. Chiunque può impersonare qualsiasi utente specificando un `user_id` arbitrario.

### Componenti per Utente

#### 1. TreeManager
**File**: `elysia/api/services/tree.py`

Gestisce **multiple conversazioni** (Tree) per un singolo utente:

```python
TreeManager.trees = {
    "conversation_id_1": Tree,  # Istanza Tree con TreeData, history, environment
    "conversation_id_2": Tree,
    ...
}
```

**Contenuto di ogni Tree**:
- `TreeData`: storia conversazione, environment (oggetti recuperati), tasks completati
- `Settings`: API keys LLM, modelli (base/complex), configurazioni provider
- Stato decisionale: branch corrente, recursion counter, action log

#### 2. ClientManager
**File**: `elysia/util/client.py`

Gestisce le **connessioni Weaviate** (sync e async) per l'utente:
- Client HTTP (porta 8080) e gRPC (porta 50051) verso Weaviate
- Cache delle connessioni con auto-restart dopo `client_timeout` minuti di inattività
- Configurato con credenziali Weaviate dell'utente (o default da `.env`)

**Metodi chiave**:
- `connect_to_client()` / `connect_to_async_client()`: context manager per connessioni
- `restart_client()`: riconnessione automatica se idle troppo a lungo
- `close_clients()`: chiusura pulita

#### 3. FrontendConfig
**File**: `elysia/api/utils/config.py`

Configurazioni UI e preferenze dell'utente:

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `tree_timeout` | 20 min | Tempo di inattività prima che una conversazione venga rimossa dalla memoria |
| `client_timeout` | 5 min | Tempo di inattività prima che il client Weaviate venga chiuso |
| `save_trees_to_weaviate` | false | Se salvare automaticamente le conversazioni in Weaviate al termine |
| `save_location_client_manager` | None | ClientManager per il cluster Weaviate dove salvare (può differire da quello di query) |

**Caricamento**: da file locale `elysia/api/user_configs/frontend_config_{user_id}.json` se esiste, altrimenti default.

#### 4. last_request
Timestamp `datetime.datetime` dell'ultima richiesta HTTP/WebSocket dell'utente. Usato per:
- Timeout utente (default 20 minuti, configurabile via `USER_TIMEOUT` env var)
- Tenere l'utente "attivo" in memoria

## Ciclo di Vita di una Richiesta

### 1. Inizializzazione Utente

**Endpoint**: `POST /init/user/{user_id}` (`elysia/api/routes/init.py`)

```python
await user_manager.add_user_local(user_id, config=None)
```

**Cosa succede** (righe 155-187):
1. Se `user_id` non esiste in `self.users`, crea nuova entry
2. Carica `FrontendConfig` da file se esiste (riga 172)
3. Crea `TreeManager` con il config (riga 176-180)
4. Crea `ClientManager` con le settings del TreeManager (riga 183-187)

**Dati iniziali**: tutto da `.env` o default, nessuna conversazione attiva.

### 2. Inizializzazione Conversazione

**Chiamata interna** (prima di processare una query):

```python
tree = await user_manager.initialise_tree(user_id, conversation_id, low_memory=False)
```

**Cosa succede** (righe 290-316):
1. Assicura che l'utente esista (chiama `add_user_local`)
2. Ottiene il `TreeManager` dell'utente
3. Se `conversation_id` non esiste, chiama `TreeManager.add_tree()`
4. Ritorna l'istanza `Tree` (nuova o esistente)

**Risultato**: un `Tree` vuoto pronto a processare query.

### 3. Processamento Query

**Endpoint**: `WebSocket /ws/query` (`elysia/api/routes/query.py`)

```python
async for result in user_manager.process_tree(
    user_id=data["user_id"],
    conversation_id=data["conversation_id"],
    query=data["query"],
    query_id=data["query_id"],
    collection_names=data["collection_names"],
    disable_rag=False
):
    await websocket.send_json(result)
```

**Flow dettagliato** (righe 529-609):

1. **Controllo timeout utente** (righe 568-574)
   - Se utente idle > `user_timeout` → yield `UserTimeoutError`
   - Return

2. **Controllo timeout conversazione** (righe 576-585)
   - Se conversazione non in memoria:
     - Prova a ricaricare da Weaviate (`ELYSIA_TREES__` collection)
     - Se non esiste → yield `TreeTimeoutError`
   - Return se errore

3. **Ottieni user locale** (riga 587)
   - Chiama `get_user_local(user_id)` che aggiorna anche `last_request`

4. **Delega al TreeManager** (righe 590-602)
   - Chiama `tree_manager.process_tree()` → `Tree.async_run()`
   - Yielda ogni risultato in streaming (Response, Result, Retrieval, Error, ecc.)
   - Aggiorna `last_request` ad ogni yield

5. **Salvataggio automatico** (righe 604-609)
   - Se `save_trees_to_weaviate == true` nel FrontendConfig
   - Salva l'intera conversazione in Weaviate (`ELYSIA_TREES__`)

### 4. Background Tasks

**File**: `elysia/api/app.py`

Lo scheduler avvia task periodici (ogni 5 minuti):

```python
# Scheduler 1: Cleanup conversazioni inattive
await user_manager.check_all_trees_timeout()
# Rimuove Tree da TreeManager.trees se idle > tree_timeout

# Scheduler 2: Cleanup utenti inattivi
await user_manager.check_all_users_timeout()
# Rimuove utente da self.users se idle > user_timeout

# Scheduler 3: Riconnessione client Weaviate
await user_manager.check_restart_clients()
# Chiude e riapre client se idle > client_timeout
```

## Gestione Dati

### Dati in Memoria (volatili, persi al riavvio)

| Dato | Origine | Dove memorizzato |
|------|---------|------------------|
| `user_id` | Client (payload WebSocket/REST) | Chiave `self.users` |
| `conversation_id` | Client (payload) | Chiave `TreeManager.trees` |
| Conversation history | Accumulata durante query | `Tree.tree_data.conversation_history` |
| Environment | Oggetti recuperati dai tool | `Tree.tree_data.environment` |
| Settings (API keys, modelli) | `.env` → `Config` → `TreeManager.settings` | `TreeManager.config.settings` |
| FrontendConfig | File JSON locale | `self.users[user_id]["frontend_config"]` |
| Client Weaviate | Connessioni attive | `ClientManager._client` / `._async_client` |

### Dati Persistenti

#### Su Disco
- **FrontendConfig**: `elysia/api/user_configs/frontend_config_{user_id}.json`
- **Settings custom**: Salvate in Weaviate `ELYSIA_CONFIG__` (cifrate con Fernet, via endpoint `/user/config`)

#### In Weaviate

| Collection | Contenuto | Filtro per utente |
|------------|-----------|-------------------|
| `ELYSIA_TREES__` | Conversazioni salvate (intero `Tree.tree_data` serializzato) | Property `user_id` |
| `ELYSIA_CONFIG__` | Configurazioni custom utente (API keys, settings) | Property `user_id` |
| `ELYSIA_METADATA__` | Metadata collezioni preprocessate | **NO** (condiviso) |
| Altre collezioni (es. `Documents`) | Dati RAG | **NO** (condiviso) |

**Recupero conversazioni salvate**:
```python
saved_trees = await user_manager.get_saved_trees(user_id)
# Ritorna dict {conversation_id: {"title": "...", "last_update_time": "..."}}
```

## Metodi Principali

### Gestione Utenti

| Metodo | Descrizione |
|--------|-------------|
| `add_user_local(user_id, config)` | Crea utente con TreeManager, ClientManager, FrontendConfig |
| `get_user_local(user_id)` | Ritorna dict utente, aggiorna `last_request` |
| `user_exists(user_id)` | Check esistenza |
| `check_user_timeout(user_id)` | Verifica se idle > `user_timeout` |
| `check_all_users_timeout()` | Rimuove tutti gli utenti idle |

### Gestione Conversazioni

| Metodo | Descrizione |
|--------|-------------|
| `initialise_tree(user_id, conversation_id, low_memory)` | Crea Tree per conversazione |
| `get_tree(user_id, conversation_id)` | Ritorna istanza Tree |
| `process_tree(user_id, conversation_id, query, ...)` | **Metodo core**: esegue query e streama risultati |
| `check_tree_timeout(user_id, conversation_id)` | Verifica se conversazione in memoria |
| `check_all_trees_timeout()` | Rimuove Tree idle da tutti gli utenti |

### Persistenza Conversazioni

| Metodo | Descrizione |
|--------|-------------|
| `save_tree(user_id, conversation_id, wcd_url, wcd_api_key)` | Salva Tree in Weaviate |
| `load_tree(user_id, conversation_id, wcd_url, wcd_api_key)` | Carica Tree da Weaviate |
| `delete_tree(user_id, conversation_id, wcd_url, wcd_api_key)` | Elimina da Weaviate e memoria |
| `check_tree_exists_weaviate(user_id, conversation_id, ...)` | Verifica esistenza in Weaviate |
| `get_saved_trees(user_id, wcd_url, wcd_api_key)` | Lista tutte le conversazioni salvate per utente |

### Configurazione

| Metodo | Descrizione |
|--------|-------------|
| `update_config(user_id, conversation_id, config_id, ...)` | Aggiorna Settings del TreeManager (API keys, modelli, ecc.) |
| `update_frontend_config(user_id, config)` | Aggiorna FrontendConfig (timeout, save location, ecc.) |

## Timeout e Pulizia

### User Timeout
- **Default**: 20 minuti (env var `USER_TIMEOUT`)
- **Trigger**: `check_all_users_timeout()` eseguito periodicamente
- **Azione**: rimozione completa dell'utente da `self.users`
- **Nota**: attualmente **disabilitato** nel codice (righe 249-254 commentate)

### Tree Timeout
- **Default**: 20 minuti (da `FrontendConfig.tree_timeout`)
- **Trigger**: `check_all_trees_timeout()` eseguito periodicamente
- **Azione**: rimozione del Tree da `TreeManager.trees`
- **Recupero**: se la conversazione è salvata in Weaviate, viene automaticamente ricaricata al prossimo accesso

### Client Timeout
- **Default**: 5 minuti (da `FrontendConfig.client_timeout`)
- **Trigger**: `check_restart_clients()` eseguito periodicamente
- **Azione**: chiusura e riapertura del client Weaviate
- **Scopo**: evitare connection leak e problemi di stale connections

## Considerazioni per Multi-Tenancy

### Stato Attuale (NON multi-tenant)

1. **Nessuna autenticazione**: `user_id` è client-provided, non validato
2. **Isolamento solo in memoria**: ogni `user_id` ha stato separato in `self.users`, ma:
   - Chiunque può impersonare qualsiasi utente
   - Tutti condividono lo stesso cluster Weaviate
3. **Collezioni condivise**: nessun filtro per organizzazione, tutti vedono tutte le collezioni
4. **Conversazioni isolate**: solo se `conversation_id` è univoco
5. **Dati salvati filtrati per `user_id`**: `ELYSIA_TREES__` e `ELYSIA_CONFIG__` hanno property `user_id`, ma senza auth è aggirabile

### Modifiche Necessarie per Multi-Tenancy Reale

Vedere `MULTI_TENANT_PLAN.md` per il piano completo. In sintesi:

1. **Validazione JWT**: middleware che valida token Supabase e popola `request.state.user_id` verificato
2. **Mapping org→user**: aggiungere `organization_id` al dict utente in `self.users[user_id]`
3. **Filtraggio collezioni**: in `get_user_local()`, caricare le collezioni permesse per l'organizzazione dell'utente
4. **AuthService**: nuovo servizio che:
   - Valida JWT
   - Mantiene cache `user_id → allowed_collections`
   - Fa query a Supabase per ottenere `organization_id` e mapping

## Diagramma di Flusso

```
┌─────────────┐
│  WebSocket  │
│  /ws/query  │
└──────┬──────┘
       │
       ▼
┌────────────────────────────────────┐
│ user_manager.process_tree()       │
├────────────────────────────────────┤
│ 1. Check user timeout              │
│ 2. Check tree timeout (reload?)    │
│ 3. get_user_local(user_id)         │
│    └─> Update last_request         │
│ 4. tree_manager.process_tree()     │
│    └─> tree.async_run()            │
│       └─> DecisionNode → Tools     │
│          └─> yield Results         │
│ 5. Save to Weaviate (if enabled)   │
└────────────────────────────────────┘
       │
       ▼
┌─────────────────┐
│ WebSocket.send  │
│ (streaming)     │
└─────────────────┘
```

## File Correlati

- **Core**: `elysia/api/services/user.py` (questo file)
- **TreeManager**: `elysia/api/services/tree.py`
- **ClientManager**: `elysia/util/client.py`
- **FrontendConfig**: `elysia/api/utils/config.py`
- **Config/Settings**: `elysia/config.py`
- **Endpoint init**: `elysia/api/routes/init.py`
- **Endpoint query**: `elysia/api/routes/query.py`
- **Dependency injection**: `elysia/api/dependencies/common.py` (singleton `get_user_manager()`)

## Esempio di Utilizzo

```python
# FastAPI app startup
user_manager = UserManager(user_timeout=20)  # 20 minuti

# WebSocket handler
@router.websocket("/ws/query")
async def query_endpoint(websocket: WebSocket, user_manager: UserManager = Depends(get_user_manager)):
    data = await websocket.receive_json()

    # Inizializza utente se non esiste
    await user_manager.add_user_local(data["user_id"])

    # Inizializza conversazione se non esiste
    await user_manager.initialise_tree(data["user_id"], data["conversation_id"])

    # Processa query e streama risultati
    async for result in user_manager.process_tree(
        user_id=data["user_id"],
        conversation_id=data["conversation_id"],
        query=data["query"],
        query_id=data["query_id"],
        collection_names=data["collection_names"]
    ):
        await websocket.send_json(result)
```

## Note Finali

- **Singleton pattern**: una sola istanza di `UserManager` per tutta l'applicazione
- **Thread-safe**: no, assume single-process asyncio (non usare con Gunicorn workers > 1)
- **Scalabilità**: limitata alla memoria del processo, non distribuita
- **Persistenza**: solo via Weaviate, non su DB relazionale
- **Security**: **CRITICA** - attualmente nessuna autenticazione, implementare prima di produzione
