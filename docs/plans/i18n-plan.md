# Piano i18n Completo per Athena (elysia-frontend + elysia backend)

## Context

L'attuale gestione delle lingue in Athena è frammentaria: solo 4 stringhe sono tradotte (in `branding.ts`), ~60+ stringhe UI sono hardcoded (mix italiano/inglese), i messaggi di stato del backend sono in inglese fisso, e i prompt suggeriti vengono generati in una sola lingua durante il preprocessing. L'obiettivo è che **tutto ciò che l'utente vede** sia nella sua `preferred_language` (IT o EN), indipendentemente dalla lingua del prompt.

## Decisioni di design confermate

- **Frontend i18n**: `next-intl` (nativo Next.js, file JSON per locale)
- **Prompt suggeriti**: pre-generati in entrambe le lingue durante il preprocessing
- **Messaggi di stato backend**: il backend invia chiavi (es. `status.thinking`), il frontend traduce
- **Scope**: tutto il frontend (tutte le pagine)

---

## Fase 1: Setup next-intl (Foundation)

### 1.1 Installare next-intl
```bash
cd elysia-frontend && npm install next-intl
```

### 1.2 Creare file di traduzione
Creare `elysia-frontend/messages/en.json` e `elysia-frontend/messages/it.json` con namespace organizzati per area funzionale:

```
messages/
  en.json   # Tutte le stringhe in inglese
  it.json   # Tutte le stringhe in italiano
```

**Namespace suggeriti** (dentro ogni JSON):
- `common` — Loading, Cancel, OK, Save, Delete, error generico
- `sidebar` — Chat, Data, Settings, Evaluation, Reportistica, Prompt Enhancer
- `chat` — askTitle, placeholder, relatedQuestions, New Conversation, mode labels
- `conversations` — Loading conversations, Add Conversation, Delete
- `socket` — Connected to Atena, Connection lost
- `status` — thinking, querying, aggregating, summarizing, writingResponse, visualising, running
- `queryInput` — route placeholder, mimicking toggle, RAG toggle
- `rateLimit` — titolo, descrizione, newsletter
- `profile` — tutte le label del profilo (~20 stringhe)
- `data` — Dashboard, Import Data
- `eval` — Evaluation Dashboard, Feedback, conteggi
- `reportistica` — titoli, parametri, loading, errori
- `promptEnhancer` — Usa, Pulisci, Migliora, placeholder, errori
- `config` — Loading config, providers, models, unsaved changes
- `userNav` — Guest, Profile, Log out
- `toast` — analyzing, done, connectionLost, analysisRemoved
- `ethicalGuard` — messaggio blocco etico

### 1.3 Creare I18nProvider
Nuovo file: `elysia-frontend/app/components/contexts/I18nContext.tsx`

- Importa staticamente entrambi i JSON (solo 2 lingue, dimensione trascurabile)
- Legge `preferred_language` da `useUserProfile()` (che dipende da `SessionContext`)
- Wrappa i children con `NextIntlClientProvider locale={lang} messages={messages[lang]}`
- Fallback a `"it"` prima che il profilo sia caricato

### 1.4 Inserire I18nProvider nel provider chain
In `elysia-frontend/app/layout.tsx`, inserire `I18nProvider` **dopo AuthProvider, prima di AuthGuard**:

```
ThemeProvider > Suspense > ToastProvider > RouterProvider > SessionProvider >
  CollectionProvider > ConversationProvider > SocketProvider > EvaluationProvider >
    ProcessingProvider > AuthProvider > **I18nProvider** > AuthGuard > AppShell
```

> **Nota**: `ToastProvider` e `SocketContext` usano stringhe hardcoded ma sono sopra `I18nProvider`. Due opzioni:
> - Spostare `I18nProvider` più in alto (ma serve il session/user ID)
> - Per Toast/Socket, usare un approccio ibrido: passare le chiavi e tradurle nel punto di visualizzazione (non nel provider)
>
> **Approccio consigliato**: i toast e gli status vengono memorizzati come chiavi, tradotti nel componente che li renderizza (es. il `Toaster` component e il `QueryInput` che mostra lo status). Questo evita di riordinare i provider.

### 1.5 Aggiornare `<html lang>`
In `layout.tsx`, cambiare `<html lang="en">` per riflettere la lingua attiva. Poiché `layout.tsx` è un Server Component, si può usare un Client Component wrapper che legge la lingua dal context e aggiorna `document.documentElement.lang`.

---

## Fase 2: Estrazione stringhe frontend (per pagina)

Ogni componente viene migrato sostituendo le stringhe hardcoded con `useTranslations('namespace')`. Ordine:

### 2.1 Componenti core (usati ovunque)
- `app/components/dialog/ConfirmationModal.tsx` — "Cancel", "OK"
- `components/user-nav.tsx` — "Guest (Login)", "Profile", "Log out"

### 2.2 Navigazione
- `app/components/navigation/SidebarComponent.tsx` — 6 label sidebar
- `app/components/navigation/HomeSubMenu.tsx` — "Conversations", "Add Conversation", "Delete", loading
- `app/components/navigation/DataSubMenu.tsx` — "Dashboard", "Import Data"
- `app/components/navigation/SettingsSubMenu.tsx` — "Configuration", "Blob"
- `app/components/navigation/EvalSubMenu.tsx` — "Dashboard", "Feedback", "Displays"
- `app/components/navigation/RateLimitDialog.tsx` — tutto il dialogo rate limit

### 2.3 Chat
- `app/pages/ChatPage.tsx` — "Loading Atena...", mode labels, "New Conversation", errori
- `app/components/chat/QueryInput.tsx` — placeholder, mimicking, RAG toggle, **status display**
- `app/components/chat/displays/SystemMessages/RateLimitMessageDisplay.tsx`
- Rimuovere `CHAT_I18N` da `branding.ts` e la prop `preferredLanguage` da QueryInput

### 2.4 Profilo
- `app/pages/ProfilePage.tsx` — ~20+ stringhe italiane hardcoded → tutte in `profile` namespace

### 2.5 Altre pagine
- `app/pages/ReportisticaPage.tsx` — tutte le label, errori, placeholder
- `app/pages/PromptEnhancerPage.tsx` — pulsanti, placeholder, errori
- `app/pages/EvalPage.tsx` — dashboard labels, feedback conteggi
- `app/pages/SettingsPage.tsx` — loading, errori, unsaved changes
- `app/pages/DataPage.tsx` / `DataDashboard.tsx` — label explorer

### 2.6 Configurazione
- `app/components/configuration/TreeSettingsView.tsx`
- `app/components/configuration/sections/ModelsSection.tsx`
- `app/components/configuration/ConfigNameEditor.tsx`
- `app/components/configuration/ConfigSidebar.tsx`
- Altre sezioni config (WeaviateSection, StorageSection, AgentSection, etc.)

### 2.7 Context (stringhe come chiavi)
- `app/components/contexts/SocketContext.tsx` — "Connected to Atena", "Connection lost" → salvare come chiavi, tradurre nel punto di rendering
- `app/components/contexts/ToastContext.tsx` — errori generici → chiavi
- `app/components/contexts/CollectionContext.tsx` — toast di analisi → chiavi

### 2.8 Layout
- `app/layout.tsx` — Suspense fallback "Loading..."

---

## Fase 3: Backend — messaggi di stato come chiavi

### 3.1 Cambiare tutte le stringhe di status nei tool

| File | Attuale | Nuova chiave |
|------|---------|-------------|
| `elysia/tools/text/direct_answer.py:22` | `"Thinking..."` | `"status.thinking"` |
| `elysia/tools/retrieval/query.py:62` | `"Querying..."` | `"status.querying"` |
| `elysia/tools/retrieval/aggregate.py:48` | `"Aggregating..."` | `"status.aggregating"` |
| `elysia/tools/text/text.py:34,92` | `"Summarizing..."` | `"status.summarizing"` |
| `elysia/tools/text/text.py:138,182` | `"Writing response..."` | `"status.writingResponse"` |
| `elysia/tools/visualisation/visualise.py:30` | `"Visualising..."` | `"status.visualising"` |
| `elysia/tools/visualisation/linear_regression.py:23` | `"Running linear regression..."` | `"status.runningLinearRegression"` |
| `elysia/tree/util.py:279` | `f"Running {id}..."` | `"status.running"` + `params: {"tool": id}` |

### 3.2 Formato WebSocket per status parametrizzati
Aggiungere campo opzionale `params` al payload status:

```json
{"type": "status", "payload": {"text": "status.running", "params": {"tool": "query"}}}
```

### 3.3 Frontend — risoluzione chiavi status
In `QueryInput.tsx` (dove viene mostrato `currentStatus`):
```typescript
const t = useTranslations('status');
const statusText = currentStatus.startsWith('status.')
  ? t(currentStatus.replace('status.', ''), params)
  : currentStatus; // fallback per stringhe raw
```

Aggiornare il tipo `TextPayload` in `app/types/chat.ts`:
```typescript
export interface TextPayload {
  text: string;
  params?: Record<string, string>;
}
```

---

## Fase 4: Prompt suggeriti bilingui

### 4.1 Modificare preprocessing
In `elysia/preprocessing/collection.py`, funzione `preprocess_async()`:
- Chiamare `_suggest_prompts()` **due volte**: una con `language="it"`, una con `language="en"`
- Salvare come `out["prompts_it"]` e `out["prompts_en"]`
- Mantenere `out["prompts"] = out["prompts_it"]` per backward compatibility

### 4.2 Schema Weaviate metadata
Aggiungere proprietà esplicite nella definizione dello schema `ELYSIA_METADATA__`:
```python
Property(name="prompts_it", data_type=DataType.TEXT_ARRAY),
Property(name="prompts_en", data_type=DataType.TEXT_ARRAY),
```

### 4.3 Servire i prompt nella lingua giusta
In `elysia/api/routes/collections.py`, endpoint che serve i metadati delle collection:
```python
preferred_language = user_data.get("preferred_language", "it")
lang_key = f"prompts_{preferred_language}"
item["prompts"] = item.get(lang_key) or item.get("prompts", [])
```

### 4.4 Rimuovere traduzione on-the-fly
Eliminare `_TranslatePromptsSignature`, `_translate_prompts()`, e `_prompt_translation_cache` dato che i prompt sono ora pre-generati in entrambe le lingue.

### 4.5 Migration: collection esistenti
Le collection già preprocessate avranno solo il campo `prompts`. Il fallback in 4.3 gestisce questo caso. Per rigenerare: ri-preprocessare le collection.

---

## Fase 5: Ethical guard e altri messaggi backend

### 5.1 Ethical guard
In `elysia/api/routes/utils.py:282`, il messaggio hardcoded in italiano:
```python
# Da:
"Non è possibile migliorare questo prompt in quanto..."
# A: restituire chiave + parametri
{"feedback_key": "ethicalGuard.blocked", "feedback_params": {"category": violated_category}}
```

Nel frontend `PromptEnhancerPage.tsx`, verificare `feedback_key` e tradurre.

---

## Fase 6: Cleanup e verifica

### 6.1 Rimozioni
- Rimuovere `CHAT_I18N` da `app/config/branding.ts`
- Rimuovere la prop `preferredLanguage` da `QueryInput` (ora usa `useTranslations`)
- Rimuovere import/riferimenti a `CHAT_I18N` da `ChatPage.tsx` e `QueryInput.tsx`

### 6.2 Verifica
- Cambiare lingua nel profilo → verificare che TUTTE le pagine si aggiornino
- Testare con `npm run build` (server mode)
- Testare con `npm run assemble` (static export) — verificare che le traduzioni siano incluse nel bundle
- Verificare che le risposte LLM rispettino la lingua del profilo indipendentemente dalla lingua del prompt
- Verificare che i prompt suggeriti appaiano nella lingua corretta
- Verificare i messaggi di stato durante una query ("Sto pensando...", "Interrogazione...", etc.)

---

## File critici da modificare

### Frontend
| File | Modifica |
|------|----------|
| `elysia-frontend/package.json` | Aggiungere `next-intl` |
| `elysia-frontend/messages/en.json` | **NUOVO** — tutte le stringhe EN |
| `elysia-frontend/messages/it.json` | **NUOVO** — tutte le stringhe IT |
| `elysia-frontend/app/components/contexts/I18nContext.tsx` | **NUOVO** — I18nProvider |
| `elysia-frontend/app/layout.tsx` | Inserire I18nProvider nel chain |
| `elysia-frontend/app/config/branding.ts` | Rimuovere CHAT_I18N |
| `elysia-frontend/app/pages/ChatPage.tsx` | useTranslations, rimuovere CHAT_I18N |
| `elysia-frontend/app/pages/ProfilePage.tsx` | useTranslations per ~20 stringhe |
| `elysia-frontend/app/pages/ReportisticaPage.tsx` | useTranslations |
| `elysia-frontend/app/pages/PromptEnhancerPage.tsx` | useTranslations + ethical guard key |
| `elysia-frontend/app/pages/EvalPage.tsx` | useTranslations |
| `elysia-frontend/app/pages/SettingsPage.tsx` | useTranslations |
| `elysia-frontend/app/components/chat/QueryInput.tsx` | useTranslations, status key resolution |
| `elysia-frontend/app/components/navigation/SidebarComponent.tsx` | useTranslations |
| `elysia-frontend/app/components/navigation/HomeSubMenu.tsx` | useTranslations |
| `elysia-frontend/app/components/navigation/RateLimitDialog.tsx` | useTranslations |
| `elysia-frontend/app/components/contexts/SocketContext.tsx` | Chiavi invece di stringhe |
| `elysia-frontend/app/components/dialog/ConfirmationModal.tsx` | useTranslations |
| `elysia-frontend/app/types/chat.ts` | Aggiungere `params` a TextPayload |
| `elysia-frontend/components/user-nav.tsx` | useTranslations |
| + tutti gli altri componenti con stringhe hardcoded |

### Backend
| File | Modifica |
|------|----------|
| `elysia/tools/text/direct_answer.py` | status → "status.thinking" |
| `elysia/tools/retrieval/query.py` | status → "status.querying" |
| `elysia/tools/retrieval/aggregate.py` | status → "status.aggregating" |
| `elysia/tools/text/text.py` | status → chiavi |
| `elysia/tools/visualisation/visualise.py` | status → "status.visualising" |
| `elysia/tools/visualisation/linear_regression.py` | status → chiave |
| `elysia/tree/util.py` | status → "status.running" + params |
| `elysia/preprocessing/collection.py` | Generare prompt in entrambe le lingue |
| `elysia/api/routes/collections.py` | Servire prompt nella lingua giusta |
| `elysia/api/routes/utils.py` | Ethical guard → chiave |
