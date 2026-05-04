# PRD 10: adapter chat Athena

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)
- [01-text-to-relevant-chunks.md](./01-text-to-relevant-chunks.md)
- [02-single-document-retrieval.md](./02-single-document-retrieval.md)
- [03-multi-document-retrieval.md](./03-multi-document-retrieval.md)
- [04-embedding-provider-boundary.md](./04-embedding-provider-boundary.md)
- [05-pgvector-ephemeral-index.md](./05-pgvector-ephemeral-index.md)
- [06-n8n-callable-workflow.md](./06-n8n-callable-workflow.md)
- [07-document-descriptor-provider.md](./07-document-descriptor-provider.md)
- [08-microsoft-365-provider.md](./08-microsoft-365-provider.md)
- [09-persistent-personal-cache.md](./09-persistent-personal-cache.md)

## Obiettivo

Integrare il retrieval documentale esterno nella chat Athena dopo che la pipeline di retrieval è stabile in modo indipendente.

Questo è il primo step in cui `conversation_id`, `query_id`, stati WebSocket e arricchimento prompt Athena diventano rilevanti.

Il contesto mini-RAG documentale non vale solo per il primo prompt. I documenti selezionati devono restare associati alla conversazione e devono supportare tutti i prompt successivi fino a quando l'utente apre o crea una nuova conversazione.

Questo mini-RAG non disabilita automaticamente il RAG standard Athena/Weaviate. I chunk dei documenti spot arricchiscono prima il prompt; poi il prompt arricchito entra nel normale flusso Athena. Se l'utente ha attivato il RAG generale, il flusso Athena continua a usare anche Weaviate e i documenti già indicizzati in Athena.

## Flusso utente

1. L'utente seleziona documenti nella UI chat.
2. L'utente scrive un prompt.
3. L'utente invia una sola volta.
4. Athena riceve prompt più descrittori documento.
5. Athena chiama il workflow di retrieval documentale.
6. Athena arricchisce il prompt con i chunk restituiti.
7. Athena esegue il normale flusso chat sul prompt arricchito.
8. Ai prompt successivi, Athena riusa il contesto documentale già associato alla conversazione.
9. Se l'utente aggiunge altri documenti, Athena estende il contesto RAG della conversazione.
10. Se l'utente ha attivato il RAG generale, il flusso standard Athena usa anche Weaviate.

## Requisiti

- Estendere il payload chat con `external_documents`.
- Non disabilitare automaticamente il normale RAG Weaviate Athena quando sono presenti documenti esterni.
- Applicare il mini-RAG documentale come arricchimento preliminare del prompt.
- Dopo l'arricchimento, rispettare la scelta RAG dell'utente per il flusso standard Athena.
- Se il RAG generale è attivo, combinare mini-RAG documentale e retrieval Weaviate nel normale flusso Athena.
- Persistire nello stato della conversazione l'elenco dei documenti esterni attivi.
- Applicare il retrieval documentale a ogni query della conversazione finché il contesto resta attivo.
- Resettare il contesto documentale quando cambia o nasce una nuova conversazione.
- Permettere aggiunta incrementale di documenti durante la conversazione.
- Mantenere l'arricchimento prompt sul backend, non nel browser.
- Mostrare stati di avanzamento per preparazione documenti e retrieval.
- Conservare metadati sorgente per citazioni nel frontend.

## Validazione

I test devono verificare l'integrazione tra mini-RAG documentale e flusso Athena, non solo il retrieval isolato.

Condizioni di validazione:

- il primo prompt con documenti crea il contesto documentale della conversazione;
- i prompt successivi riusano quel contesto anche senza nuovi documenti nel payload;
- una nuova conversazione parte senza il contesto della conversazione precedente;
- aggiungere documenti durante la conversazione estende il contesto;
- il RAG generale Athena resta governato dalla scelta dell'utente;
- con RAG generale attivo, il prompt arricchito passa al normale retrieval Weaviate;
- con RAG generale non attivo, il mini-RAG documentale resta disponibile ma Weaviate generale non viene interrogato;
- fonti dei documenti spot restano distinguibili dalle fonti Weaviate.

La validazione LLM può valutare la risposta finale per verificare che usi correttamente il contesto documentale spot e, quando previsto, il contesto Weaviate.

## Harness di test

L'harness deve simulare una conversazione completa:

1. creazione conversazione;
2. primo prompt con documenti;
3. secondo prompt senza documenti;
4. aggiunta di un nuovo documento;
5. prompt con RAG generale attivo;
6. prompt con RAG generale non attivo;
7. nuova conversazione con contesto resettato.

Il wrapper deve simulare il payload chat reale, incluso:

- `conversation_id`;
- `query_id`;
- prompt;
- documenti esterni;
- flag o stato dell'opzione RAG generale;
- risposte mock del servizio documentale;
- eventuali risposte mock del retrieval Weaviate.

## TDD e riuso

Lo step deve usare il servizio documentale validato nei PRD precedenti. Non deve reimplementare retrieval, cache, provider Microsoft 365 o pgvector.

Le modifiche devono limitarsi ad adapter chat, stato conversazione, orchestrazione del prompt arricchito e integrazione con il flusso Athena esistente.

## Fuori scope

- Costruzione del Microsoft File Picker.
- Implementazione della pipeline low-level di retrieval.
- Progettazione di un prodotto completo di gestione documentale.
