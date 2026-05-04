# PRD 06: workflow n8n invocabile

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)
- [01-text-to-relevant-chunks.md](./01-text-to-relevant-chunks.md)
- [02-single-document-retrieval.md](./02-single-document-retrieval.md)
- [03-multi-document-retrieval.md](./03-multi-document-retrieval.md)
- [04-embedding-provider-boundary.md](./04-embedding-provider-boundary.md)
- [05-pgvector-ephemeral-index.md](./05-pgvector-ephemeral-index.md)

## Obiettivo

Esporre la pipeline di retrieval tramite n8n in modo che possa essere testata indipendentemente da Athena.

In questo step il workflow riceve ancora testo grezzo o semplici oggetti documento. Non recupera file da Microsoft 365.

## Ingresso

```json
{
  "prompt": "Quali sono i punti più rilevanti?",
  "documents": [
    {
      "name": "documento.txt",
      "text": "Contenuto..."
    }
  ]
}
```

## Uscita

```json
{
  "chunks": [
    {
      "document_name": "documento.txt",
      "chunk_index": 1,
      "text": "Chunk pertinente...",
      "score": 0.83
    }
  ]
}
```

## Requisiti

- n8n può essere invocato tramite webhook.
- n8n orchestra embedding e storage/retrieval pgvector.
- Il workflow restituisce JSON strutturato.
- Un wrapper può simulare data entry e selezione documenti.

## Validazione

I test devono dimostrare che n8n espone la stessa capacità già validata negli step precedenti, senza cambiare il contratto semantico.

Condizioni di validazione:

- il webhook accetta prompt e documenti nello stesso formato del PRD 03;
- l'output contiene chunk, score e provenienza;
- i risultati sono semanticamente coerenti con quelli del wrapper non-n8n sulle stesse fixture;
- errori di embedding, pgvector o workflow producono risposta JSON strutturata;
- il workflow può essere invocato più volte senza contaminazione tra test.

La validazione LLM può confrontare output n8n e output locale per verificare che entrambi rispondano allo stesso bisogno informativo del prompt.

## Harness di test

Lo step deve includere un wrapper client che simula il chiamante futuro di Athena:

- costruisce payload JSON realistici;
- chiama il webhook n8n;
- registra request e response;
- valida schema e pertinenza;
- può usare fixture locali per documenti e prompt;
- può girare in modalità mock se n8n non è disponibile.

Il wrapper deve essere progressivamente riusabile dagli step successivi come client del servizio documentale.

## TDD e riuso

Il workflow n8n deve orchestrare la pipeline già costruita nei PRD 01-05.

Non deve introdurre una seconda implementazione divergente del chunking, dell'embedding o del retrieval pgvector. Eventuali nodi n8n devono essere configurati per rispettare gli stessi contratti di input/output.

## Fuori scope

- Microsoft File Picker.
- Microsoft Graph.
- WebSocket Athena.
- Cache utente persistente.
