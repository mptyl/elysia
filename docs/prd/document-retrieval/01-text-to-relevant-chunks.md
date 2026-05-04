# PRD 01: testo verso chunk rilevanti

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)

## Obiettivo

Dato un testo grezzo e un prompt utente, restituire i chunk del testo più rilevanti rispetto al prompt.

Questo è lo step zero. Deve essere testabile senza documenti, n8n, Microsoft Graph, Supabase, chat Athena, utenti o conversazioni.

## Ingresso

```json
{
  "prompt": "Quali obblighi operativi emergono dal testo?",
  "text": "Contenuto lungo da analizzare..."
}
```

## Uscita

```json
{
  "chunks": [
    {
      "index": 3,
      "text": "Chunk pertinente...",
      "score": 0.82
    }
  ]
}
```

## Requisiti

- Dividere il testo in input in chunk deterministici.
- Calcolare embedding del prompt e dei chunk.
- Ordinare i chunk per rilevanza semantica rispetto al prompt.
- Restituire una lista breve e ordinata di chunk con score e posizione originale.
- Fornire un wrapper o un harness CLI/test che simuli l'input.

## Validazione

Un chunk è "pertinente" quando contiene informazioni che aiutano direttamente a rispondere al prompt, oppure contiene una premessa necessaria per interpretare correttamente la risposta.

I test devono verificare almeno:

- il chunk più rilevante contiene testo semanticamente collegato al prompt;
- chunk chiaramente fuori tema ricevono score inferiore ai chunk pertinenti;
- l'ordine dei chunk è coerente con il grado di rilevanza;
- l'indice del chunk corrisponde alla posizione originale nel testo;
- il sistema restituisce una lista vuota o un risultato a bassa confidenza quando il testo non contiene informazioni utili.

Per i casi semantici non verificabili con semplice confronto stringa, la validazione può usare un LLM come giudice. Il giudice deve ricevere prompt, testo completo, chunk restituiti e criterio di valutazione. Deve rispondere con JSON strutturato, ad esempio:

```json
{
  "relevant": true,
  "reason": "Il chunk contiene gli obblighi operativi richiesti dal prompt.",
  "missing_relevant_chunks": false
}
```

Il test passa solo se il giudice conferma che i chunk restituiti sono coerenti con il prompt e non omettono evidenze più rilevanti presenti nel testo di fixture.

## Harness di test

Lo step deve includere un harness autonomo che accetta lo stesso JSON previsto in ingresso dal PRD:

```json
{
  "prompt": "...",
  "text": "..."
}
```

L'harness deve permettere:

- esecuzione con embedding fake deterministico;
- esecuzione opzionale con embedding reale;
- caricamento di fixture testuali locali;
- stampa dell'output JSON finale;
- salvataggio facoltativo di un report di valutazione.

Le fixture minime devono includere:

- un testo con risposta evidente;
- un testo con più sezioni, di cui solo una pertinente;
- un testo senza risposta;
- un testo breve sotto la soglia di chunking;
- un testo lungo con informazione rilevante in posizione centrale o finale.

## TDD e riuso

Questo è il primo step, quindi non riusa codice precedente. Deve però fissare contratti e test che gli step successivi non devono rompere.

Ogni modifica successiva alla logica di chunking, scoring o output deve mantenere compatibili i test di questo PRD, salvo modifica esplicita del contratto.

## Fuori scope

- Metadati documento.
- Documenti multipli.
- Supabase pgvector.
- n8n.
- Microsoft Graph.
- Cache.
- WebSocket Athena.
