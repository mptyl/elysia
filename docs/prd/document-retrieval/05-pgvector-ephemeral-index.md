# PRD 05: indice effimero pgvector

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)
- [01-text-to-relevant-chunks.md](./01-text-to-relevant-chunks.md)
- [02-single-document-retrieval.md](./02-single-document-retrieval.md)
- [03-multi-document-retrieval.md](./03-multi-document-retrieval.md)
- [04-embedding-provider-boundary.md](./04-embedding-provider-boundary.md)

## Obiettivo

Passare dal confronto vettoriale in-process a Supabase pgvector per un indice di retrieval effimero.

Questo step dimostra che prompt e testo del documento possono essere chunkizzati, sottoposti a embedding, salvati in pgvector, interrogati e ripuliti.

## Requisiti

- Creare uno store basato su pgvector per chunk temporanei.
- Inserire testo del chunk, embedding, nome documento e indice del chunk.
- Interrogare tramite embedding del prompt e restituire chunk ordinati.
- Supportare cleanup dell'indice temporaneo di test.
- Mantenere l'API usabile da un wrapper locale senza Athena.

## Validazione

I test devono verificare che pgvector restituisca risultati equivalenti, o semanticamente coerenti, con il ranking in-process dei PRD precedenti.

Condizioni di validazione:

- i chunk inseriti in pgvector sono gli stessi prodotti dal chunker;
- gli embedding salvati sono associati al chunk corretto;
- la query vettoriale restituisce chunk pertinenti rispetto al prompt;
- l'ordine dei risultati è compatibile con lo score di similarità;
- il cleanup rimuove i dati temporanei creati dal test;
- due esecuzioni di test non interferiscono tra loro.

Quando si usa un provider reale, una validazione LLM può giudicare la pertinenza dei chunk. Quando si usa provider fake, la validazione deve essere deterministica.

## Harness di test

L'harness deve simulare un ciclo completo:

1. ricezione prompt e documenti;
2. chunking;
3. embedding;
4. inserimento in pgvector;
5. retrieval;
6. cleanup.

Deve supportare:

- namespace o identificatore temporaneo di test;
- modalità cleanup obbligatoria;
- modalità debug che lascia i dati per ispezione manuale;
- verifica che non restino righe dopo cleanup;
- confronto opzionale con ranking in-process.

## TDD e riuso

Lo step deve usare i PRD 01-04 per chunking, struttura documento, documenti multipli e provider embedding.

pgvector deve sostituire solo il meccanismo di storage/retrieval vettoriale, non la logica di preparazione dei chunk.

## Fuori scope

- Cache personale persistente.
- Registro documentale utente.
- Orchestrazione workflow n8n.
- Accesso file Microsoft 365.

## Note

Supabase pgvector diventa l'unico vector store per questa funzionalità. n8n Simple Vector Store non viene usato come architettura di produzione.
