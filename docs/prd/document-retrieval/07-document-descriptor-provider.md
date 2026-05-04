# PRD 07: provider da descrittore documento

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

## Obiettivo

Sostituire l'input di testo grezzo con descrittori documento e un confine per il provider di contenuto.

Questo prepara il sistema a Microsoft 365 senza richiedere Graph in questo step.

## Ingresso

```json
{
  "prompt": "Trova gli obblighi nel documento.",
  "documents": [
    {
      "provider": "mock",
      "document_id": "doc-123",
      "name": "policy.txt"
    }
  ]
}
```

## Requisiti

- Definire un contratto per provider di contenuto documentale.
- Implementare un provider mock che risolve descrittori verso testi locali di test.
- Mantenere invariato l'output di retrieval rispetto ai PRD precedenti.
- Restituire un errore chiaro quando un descrittore non può essere risolto.

## Validazione

I test devono verificare che sostituire il testo grezzo con un descrittore non cambi il comportamento di retrieval.

Condizioni di validazione:

- un descrittore mock risolve sempre allo stesso testo fixture;
- a parità di testo risolto, l'output è semanticamente equivalente al PRD 06;
- descrittori mancanti o non risolvibili producono errore strutturato;
- i metadati del descrittore vengono propagati nei chunk;
- il provider non deve eseguire retrieval semantico: deve solo recuperare contenuto.

La validazione LLM può giudicare la pertinenza dei chunk, ma la risoluzione del descrittore deve essere testata in modo deterministico.

## Harness di test

L'harness deve simulare la futura selezione documenti senza usare Microsoft Graph:

```json
{
  "provider": "mock",
  "document_id": "doc-123",
  "name": "policy.txt"
}
```

Deve includere:

- registry locale di documenti mock;
- fixture con ID stabili;
- caso documento non trovato;
- caso provider non supportato;
- confronto con input raw equivalente.

## TDD e riuso

Lo step deve usare il client/workflow del PRD 06 e aggiungere solo il livello di risoluzione documento.

La pipeline successiva al recupero testo deve restare quella già validata.

## Fuori scope

- Chiamate reali Microsoft Graph.
- Autenticazione utente.
- Cache persistente.
- Selezione file frontend.
