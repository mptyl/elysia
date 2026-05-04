# PRD 08: provider Microsoft 365

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

## Obiettivo

Aggiungere un provider di contenuto Microsoft 365 capace di risolvere file selezionati da OneDrive e SharePoint in testo.

Questo step consuma descrittori file come `driveId` e `itemId`. Non definisce la UI del picker frontend.

## Ingresso

```json
{
  "prompt": "Cosa dice il documento sui controlli?",
  "documents": [
    {
      "provider": "microsoft365",
      "drive_id": "drive-id",
      "item_id": "item-id",
      "name": "policy.docx",
      "etag": "etag-value"
    }
  ]
}
```

## Requisiti

- Risolvere descrittori Microsoft 365 in testo.
- Supportare OneDrive e librerie documentali SharePoint/Teams.
- Conservare `drive_id`, `item_id`, `name` ed `etag` nei metadati.
- Restituire chunk di retrieval usando la pipeline esistente.

## Validazione

I test devono verificare che il provider Microsoft 365 sia un sostituto reale del provider mock del PRD 07.

Condizioni di validazione:

- un descrittore `drive_id + item_id` valido viene risolto in testo;
- `etag` e metadati file vengono propagati;
- file non accessibili, cancellati o non supportati producono errori strutturati;
- il testo estratto è sufficiente per il retrieval semantico;
- a parità di contenuto, l'output resta semanticamente coerente con il provider mock.

Per documenti reali, la validazione LLM può controllare che i chunk restituiti siano pertinenti al prompt e riconducibili al contenuto effettivo del file.

## Harness di test

L'harness deve simulare il più possibile l'input che arriverà dal Microsoft File Picker:

```json
{
  "provider": "microsoft365",
  "drive_id": "drive-id",
  "item_id": "item-id",
  "name": "policy.docx",
  "etag": "etag-value"
}
```

Deve supportare due modalità:

- mock Microsoft 365, con fixture locali e descrittori realistici;
- integrazione reale, con credenziali e file di test controllati.

I test reali devono usare documenti non sensibili e ripetibili.

## TDD e riuso

Lo step deve implementare un nuovo provider conforme al contratto del PRD 07.

Non deve modificare la pipeline di chunking, embedding, pgvector o n8n già validata.

## Fuori scope

- UI Microsoft File Picker.
- Integrazione chat Athena.
- UI di gestione cache persistente.
