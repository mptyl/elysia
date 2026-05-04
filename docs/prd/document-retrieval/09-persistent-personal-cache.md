# PRD 09: cache personale persistente

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

## Obiettivo

Permettere a un utente di rendere persistenti gli embedding documentali per riuso futuro.

Questa è una cache, non un prodotto completo di knowledge base personale.

## Requisiti

- Salvare metadati della cache del documento per utente e identità del file Microsoft.
- Usare `drive_id + item_id + etag` per capire se gli embedding in cache sono aggiornati.
- Riutilizzare gli embedding quando la versione in cache è corrente.
- Marcare i documenti come stale quando cambia la versione del file Microsoft.
- Aggiornare i documenti stale in modo lazy quando l'utente li usa.
- Supportare cancellazione esplicita di una cache persistente dell'utente.

## Validazione

I test devono verificare che la cache riduca re-ingestion e re-embedding senza usare contenuto obsoleto.

Condizioni di validazione:

- lo stesso documento con stesso `drive_id + item_id + etag` riusa la cache;
- lo stesso documento con `etag` diverso viene marcato stale;
- un documento stale viene aggiornato quando usato;
- la cancellazione rimuove metadati e chunk associati all'utente;
- un utente non può vedere o cancellare cache di un altro utente;
- il retrieval da cache restituisce chunk pertinenti come il retrieval da ingestion fresca.

La validazione LLM può confrontare chunk da cache e chunk da re-ingestion per verificare equivalenza semantica.

## Harness di test

L'harness deve simulare utenti e versioni documento:

- utente A e utente B;
- stesso documento con stesso `etag`;
- stesso documento con `etag` cambiato;
- documento cancellato dalla cache;
- documento persistente riusato in una nuova conversazione simulata.

Deve registrare se la pipeline ha fatto:

- cache hit;
- cache miss;
- stale refresh;
- delete.

## TDD e riuso

Lo step deve usare provider documento, n8n, pgvector e retrieval già costruiti.

La cache deve aggiungere solo decisioni di riuso, stato e cancellazione. Non deve duplicare il motore di retrieval.

## Comportamento utente

- Il primo uso dei documenti selezionati è temporaneo.
- Dopo una risposta, Athena può mostrare "Salva per riuso".
- I documenti salvati diventano visibili in un pannello minimale profilo/impostazioni.
- L'utente può cancellare le cache documento salvate.

## Fuori scope

- Gestione ricca di una libreria documentale.
- Sincronizzazione automatica in background.
- Condivisione documenti in cache tra utenti.
