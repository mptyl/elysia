# Brainstorming: tracciamento attività utenti e consumo token in Atena

## Obiettivo

Valutare la fattibilità di:

- registrare l'attività di ogni utente su Atena
- calcolare il consumo di token ogni volta che viene chiamato un LLM esterno
- distinguere il consumo di token nelle seguenti categorie:
  - gestione della verifica etica
  - uso del database vettoriale per ricerca basata su documenti
  - risposta a prompt non basato su documenti gestiti su database vettoriale

Per ogni consumo token si desidera registrare anche:

- modello utilizzato
- provider utilizzato (es. OpenRouter)
- numero di token consumati
- categoria funzionale di appartenenza

## Contesto emerso dal codice

L'analisi del repository mostra che Atena usa il backend Atena (fork di Elysia) come orchestratore dei flussi LLM/RAG.

Punti rilevanti emersi:

- Le chiamate ai modelli passano tramite `dspy.LM`, costruito in `elysia/elysia/config.py`.
- Esiste già un tracker interno dei token/costi in `elysia/elysia/util/objects.py`.
- Il tracker attuale calcola token e costi per `base_lm` e `complex_lm`, ma:
  - lavora in memoria
  - serve solo per logging interno
  - non persiste dati
  - non classifica i consumi per categoria funzionale
- Il flusso di guardrail etico è separato nel tree runtime in `elysia/elysia/tree/tree.py`.
- Il flusso di risposta non-RAG è separato tramite il tool `DirectAnswer` in `elysia/elysia/tools/text/direct_answer.py`.
- Il flusso documentale/RAG è separato nei tool di retrieval.

È inoltre emerso che:

- il backend oggi usa ancora spesso `user_id` passato dal client
- questo identificativo non è affidabile per audit serio
- nel sistema esiste già Supabase Auth, quindi l'identità corretta da usare per il tracking è il `sub` del JWT / `auth.users.id`

## Fattibilità generale

La fattibilità è alta.

Dal punto di vista tecnico, Atena ha già punti di aggancio sufficienti per intercettare e classificare le chiamate ai modelli esterni.

Le tre categorie richieste sono distinguibili:

### 1. Verifica etica

Fattibile con alta affidabilità.

Il flusso etico è già separato. In particolare:

- pre-query ethical check
- eventuale generazione di refusal
- eventuale generazione di guidance

Queste chiamate possono essere classificate come `ethical_guard`.

### 2. Uso del database vettoriale per ricerca documentale

Fattibile, ma con una precisazione importante.

La ricerca su Weaviate locale non consuma token LLM. Quindi non va confusa con il consumo token.

Si possono però tracciare i token delle chiamate LLM che fanno parte del flusso RAG, ad esempio:

- classificazione/orchestrazione
- sintesi dei documenti recuperati
- generazione della risposta finale basata sui documenti

Queste chiamate possono essere classificate come `rag_documents`.

### 3. Risposta a prompt non basato su documenti

Fattibile con alta affidabilità.

Il tool `DirectAnswer` rappresenta già un percorso applicativo separato. I token consumati in questo flusso possono essere classificati come `direct_answer`.

## Considerazioni su Weaviate locale ed embedding esterni

Weaviate è locale, quindi non introduce costi diretti di query vettoriale.

Tuttavia è stato chiarito che viene usato Cohere come provider esterno di embedding.

Questo implica che esiste una possibile quarta classe di costo tecnico:

- `embedding_external`

Questa categoria non coincide con le tre categorie generative richieste, ma può essere utile se si vuole un quadro economico completo dei flussi documentali.

Raccomandazione:

- mantenere le tre categorie richieste per le chiamate generative
- prevedere opzionalmente una categoria separata per gli embedding esterni

## Dove registrare i log

La soluzione raccomandata è usare Supabase/Postgres come storage canonico.

Motivazioni:

- Supabase è già la fonte autorevole per l'identità utente
- il dato è strutturato e si presta a query SQL, aggregazioni e report
- serve una base relazionale affidabile per audit, analisi e possibili meccanismi futuri di ripartizione costi
- Weaviate non è il posto giusto per telemetria transazionale e reporting strutturato
- i file di log applicativi possono essere utili come supporto tecnico, ma non come fonte ufficiale

Conclusione architetturale:

- storage principale: Supabase/Postgres
- opzionale: log applicativo strutturato per debugging
- non usare Weaviate come archivio principale dei consumi

## Granularità raccomandata

La granularità migliore è per singola chiamata LLM.

Ogni invocazione esterna dovrebbe generare un evento con:

- utente
- query/conversazione
- modello
- provider
- token input
- token output
- token totali
- categoria funzionale
- timestamp

Questa scelta è preferibile rispetto a un solo aggregato per richiesta utente, perché:

- una singola query può coinvolgere più chiamate LLM
- possono essere usati modelli diversi nello stesso flusso
- si mantiene piena tracciabilità
- i report aggregati possono sempre essere costruiti successivamente a partire dagli eventi atomici

## Dati da registrare

Per ogni chiamata modello esterno si raccomanda di registrare almeno:

- `user_id` autorevole da JWT Supabase
- `conversation_id`
- `query_id`
- `provider`
- `model`
- `category`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `cost_amount` se disponibile
- `created_at`
- eventuale `success/error`

Categorie minime iniziali:

- `ethical_guard`
- `rag_documents`
- `direct_answer`

Categoria opzionale aggiuntiva:

- `embedding_external`

## Considerazioni sull'identità utente

Per un tracking affidabile, la chiave utente deve essere il `sub` del JWT Supabase.

Il `user_id` passato dal client può restare al massimo come metadato secondario di correlazione o compatibilità, ma non deve essere la chiave fiduciaria del sistema di audit.

## Conclusioni finali

La richiesta è tecnicamente fattibile e il repository mostra già una struttura favorevole all'implementazione.

Conclusioni principali:

- è possibile tracciare il consumo token per utente in Atena
- è possibile distinguere i consumi nelle tre categorie richieste
- il guardrail etico e il direct answer sono già separati e quindi facilmente classificabili
- il flusso RAG è distinguibile, ma va chiarito che Weaviate locale non consuma token LLM
- gli eventuali costi di embedding esterno, ad esempio Cohere, vanno considerati separatamente
- il punto corretto per la persistenza dei log è Supabase/Postgres
- la granularità corretta è per singola chiamata LLM
- l'identità autorevole da usare è quella di Supabase Auth via JWT

In sintesi, non ci sono blocchi tecnici sostanziali. La progettazione può procedere con buona confidenza, a patto di:

- basare il tracking sull'identità JWT
- salvare eventi atomici in Postgres
- separare chiaramente token LLM, retrieval locale e embedding esterni
- mantenere le categorie funzionali come attributo esplicito di ogni evento
