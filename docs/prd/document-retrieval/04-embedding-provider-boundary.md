# PRD 04: confine del provider di embedding

## Contesto

Guarda [00-project-vision.md](./00-project-vision.md) per capire il quadro generale del progetto.

PRD precedenti:

- [00-overview.md](./00-overview.md)
- [01-text-to-relevant-chunks.md](./01-text-to-relevant-chunks.md)
- [02-single-document-retrieval.md](./02-single-document-retrieval.md)
- [03-multi-document-retrieval.md](./03-multi-document-retrieval.md)

## Obiettivo

Introdurre un confine chiaro per il provider di embedding prima di legare il sistema a Cohere.

Il codice di retrieval deve chiamare un'interfaccia di embedding, non Cohere direttamente.

## Requisiti

- Definire un contratto del provider per embedding di batch di testi e singoli prompt.
- Fornire un provider fake deterministico per i test.
- Fornire un provider reale basato su Cohere.
- Mantenere chunking e ranking indipendenti dai dettagli del provider.

## Criteri di Accettazione

- Gli stessi test di retrieval possono girare con il provider fake.
- Un percorso di integrazione reale può girare con credenziali Cohere.
- Gli errori del provider sono restituiti come fallimenti strutturati, non come retrieval vuoto silenzioso.

## Validazione

I test devono verificare che l'introduzione del provider non modifichi il comportamento funzionale dei PRD precedenti.

Condizioni di validazione:

- con provider fake deterministico, i test dei PRD 01, 02 e 03 restano ripetibili;
- con provider reale, il sistema restituisce chunk semanticamente pertinenti sulle stesse fixture;
- errori di credenziali, timeout o rate limit del provider producono errore strutturato;
- il codice di chunking e ranking non importa direttamente SDK Cohere;
- il contratto provider supporta batch di testi, non solo una chiamata per chunk.

La validazione LLM può essere usata solo per confrontare la qualità semantica dell'output con provider reale. La conformità dell'interfaccia deve essere verificata con test deterministici.

## Harness di test

L'harness deve permettere di scegliere il provider via configurazione:

- `fake`, per test deterministici e CI;
- `cohere`, per test di integrazione reale;
- eventuale modalità `dry-run`, per validare input senza chiamare servizi esterni.

Il wrapper deve produrre nello stesso formato:

- provider usato;
- numero di testi embedded;
- eventuali errori provider;
- output di retrieval.

## TDD e riuso

Lo step deve incapsulare il calcolo embedding senza riscrivere retrieval, chunking o ranking.

I test dei PRD precedenti devono essere eseguiti contro il provider fake come test di regressione.

## Fuori scope

- pgvector.
- n8n.
- Microsoft Graph.
- Cache.
