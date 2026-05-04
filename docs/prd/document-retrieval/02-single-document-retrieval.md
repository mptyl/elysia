# PRD 02: recupero su singolo documento

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)
- [01-text-to-relevant-chunks.md](./01-text-to-relevant-chunks.md)

## Obiettivo

Aggiungere il concetto minimo di documento attorno alla pipeline di recupero da testo grezzo.

Il sistema riceve un documento con nome e testo, poi restituisce chunk rilevanti con provenienza documentale.

## Ingresso

```json
{
  "prompt": "Riassumi gli obblighi indicati.",
  "document": {
    "name": "policy.txt",
    "text": "Contenuto del documento..."
  }
}
```

## Uscita

```json
{
  "document": {
    "name": "policy.txt"
  },
  "chunks": [
    {
      "document_name": "policy.txt",
      "chunk_index": 2,
      "text": "Chunk pertinente...",
      "score": 0.79
    }
  ]
}
```

## Requisiti

- Riutilizzare il comportamento di retrieval del PRD 01.
- Conservare il nome del documento in ogni chunk restituito.
- Mantenere il componente testabile con una fixture locale di testo.

## Validazione

I test devono confermare che il risultato del PRD 02 è semanticamente equivalente al PRD 01 quando il testo del documento è lo stesso.

Condizioni di validazione:

- i chunk pertinenti sono gli stessi o semanticamente equivalenti a quelli restituiti dal PRD 01;
- ogni chunk restituito contiene `document_name`;
- `document_name` corrisponde esattamente al nome ricevuto in ingresso;
- `chunk_index` resta coerente con la posizione del chunk nel testo del documento;
- un documento vuoto produce errore strutturato o lista vuota, non un risultato inventato.

La validazione LLM, quando usata, deve giudicare solo la pertinenza dei chunk rispetto al prompt e al contenuto del documento. Non deve ignorare errori di provenienza o metadati.

## Harness di test

L'harness deve accettare input con forma documento:

```json
{
  "prompt": "...",
  "document": {
    "name": "fixture.txt",
    "text": "..."
  }
}
```

Deve includere wrapper che:

- costruiscono internamente l'input del PRD 01 a partire dal documento;
- confrontano l'output semantico con quello del PRD 01;
- verificano che i metadati documento vengano propagati;
- simulano documento mancante, nome mancante e testo vuoto.

## TDD e riuso

Lo step deve usare il codice del PRD 01 come nucleo di retrieval. Non deve duplicare chunking, embedding o ranking.

Sono ammessi solo adattamenti di interfaccia per aggiungere il contenitore `document` e i metadati di provenienza.

## Fuori scope

- Documenti multipli.
- ID documento esterni.
- Persistenza database.
- Microsoft 365.
