# PRD 03: recupero su documenti multipli

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)
- [01-text-to-relevant-chunks.md](./01-text-to-relevant-chunks.md)
- [02-single-document-retrieval.md](./02-single-document-retrieval.md)

## Obiettivo

Supportare retrieval su più documenti in una sola richiesta.

Il sistema riceve un prompt e una lista di documenti con testo grezzo, poi restituisce i chunk più rilevanti tra tutti i documenti.

## Ingresso

```json
{
  "prompt": "Quali documenti parlano di obblighi di conservazione?",
  "documents": [
    {
      "name": "policy-a.txt",
      "text": "Contenuto A..."
    },
    {
      "name": "policy-b.txt",
      "text": "Contenuto B..."
    }
  ]
}
```

## Uscita

```json
{
  "chunks": [
    {
      "document_name": "policy-b.txt",
      "chunk_index": 4,
      "text": "Chunk pertinente...",
      "score": 0.86
    }
  ]
}
```

## Requisiti

- Ordinare i chunk globalmente tra tutti i documenti forniti.
- Conservare nome documento e indice del chunk.
- Restituire metadati sufficienti per citazioni successive in Athena.
- Mantenere dati di test locali e deterministici.

## Validazione

I test devono dimostrare che il ranking avviene sull'insieme dei chunk di tutti i documenti, non separatamente per documento.

Condizioni di validazione:

- se solo un documento contiene informazione pertinente, i chunk migliori vengono da quel documento;
- se più documenti contengono informazioni pertinenti, l'output può includere chunk da più fonti;
- documenti non pertinenti non devono comparire nei primi risultati salvo bassa confidenza generale;
- ogni chunk conserva `document_name` e `chunk_index`;
- l'ordine dei risultati è coerente con la pertinenza globale rispetto al prompt.

La validazione LLM deve ricevere prompt, lista documenti e chunk restituiti. Deve giudicare se i documenti sorgente scelti sono corretti e se mancano chunk più pertinenti in altri documenti.

## Harness di test

L'harness deve accettare più documenti nello stesso formato previsto dal PRD:

```json
{
  "prompt": "...",
  "documents": [
    {
      "name": "a.txt",
      "text": "..."
    }
  ]
}
```

Le fixture minime devono includere:

- due documenti, uno pertinente e uno irrilevante;
- tre documenti con evidenze distribuite;
- documenti con contenuti simili ma risposte diverse;
- duplicati o quasi duplicati;
- lista documenti vuota.

## TDD e riuso

Lo step deve usare il codice del PRD 02 per ogni documento e aggiungere solo l'aggregazione/ranking globale.

Non deve cambiare il contratto di pertinenza del PRD 01 né la provenienza documentale del PRD 02.

## Fuori scope

- Cache persistente.
- Selezione documenti Microsoft.
- ID conversazione Athena.
