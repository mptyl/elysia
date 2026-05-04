# Visione del progetto: chat Athena supportata da documenti utente

## Scopo generale

Il progetto vuole permettere a un utente Athena di fare un'intera conversazione supportata in modalità RAG su uno o più documenti scelti da lui, senza dover importare quei documenti nel vector database principale di Athena.

I documenti selezionati definiscono un contesto mini-RAG documentale della conversazione. Quel contesto resta attivo per tutti i prompt successivi della stessa conversazione e viene resettato solo quando l'utente apre o crea una nuova conversazione.

Il mini-RAG documentale non sostituisce il RAG standard Athena/Weaviate. È un arricchimento preliminare del prompt. Dopo questo arricchimento, il prompt prosegue nel normale flusso Athena: filtro etico, logiche di sistema, eventuali tool e, se l'utente ha selezionato l'opzione RAG generale, retrieval su Weaviate e sui documenti già presenti in Athena.

L'esperienza finale prevista è:

1. L'utente apre la chat Athena.
2. Clicca un piccolo bottone vicino alla finestra di chat.
3. Seleziona uno o più documenti da Microsoft 365 tramite Microsoft File Picker.
4. Scrive il prompt.
5. Invia una sola volta prompt e documenti selezionati.
6. Athena usa i documenti come contesto mini-RAG per tutta quella conversazione.
7. La risposta del modello cita o espone le fonti documentali usate.
8. Dopo la risposta, Athena può proporre di salvare la cache documentale per riuso futuro.

Il primo invio deve quindi contenere sia la domanda dell'utente sia le indicazioni dei documenti scelti. I prompt successivi della stessa conversazione devono continuare a usare lo stesso contesto documentale, anche se l'utente non seleziona di nuovo i documenti.

## Ruolo di Athena

Athena resta il punto di esperienza utente e di business logic conversazionale.

Athena deve:

- gestire la chat e lo stato della conversazione;
- ricevere prompt e descrittori dei documenti selezionati;
- associare i documenti selezionati alla conversazione corrente;
- mantenere il contesto RAG documentale attivo fino alla chiusura o al cambio conversazione;
- permettere all'utente di aggiungere altri documenti durante la conversazione;
- mostrare documenti selezionati, stati di lavorazione e fonti;
- invocare il servizio documentale prima del normale flusso di generazione Athena;
- costruire o orchestrare il prompt arricchito con i chunk restituiti;
- passare il prompt arricchito al flusso standard Athena senza disabilitare automaticamente il RAG generale;
- rispettare la scelta dell'utente sull'opzione RAG generale: se il RAG generale è attivo, il prompt arricchito deve essere usato anche dal retrieval Athena/Weaviate;
- proporre all'utente il salvataggio della cache personale;
- mostrare, in una sezione profilo/impostazioni, i documenti resi persistenti e permetterne la cancellazione.

Athena non deve diventare il motore di ingestion documentale Microsoft 365.

## Ruolo di n8n

n8n è il layer operativo per la pipeline documentale.

n8n deve:

- ricevere da Athena il prompt e la lista dei documenti;
- recuperare, quando necessario, il contenuto dei documenti;
- orchestrare chunking, embedding e retrieval;
- usare Cohere per generare embedding;
- usare Supabase pgvector come vector store;
- restituire ad Athena i chunk rilevanti, con score e provenienza;
- gestire operazioni separate come preparazione, retrieval, salvataggio cache, lista cache e cancellazione cache;
- mantenere o ricostruire il perimetro dei documenti attivi per una conversazione, in base alle indicazioni ricevute da Athena.

n8n non deve produrre direttamente l'intera esperienza chat Athena. Deve restare invocabile e testabile come componente autonomo.

## Rapporto tra mini-RAG documentale e RAG standard Athena

Il mini-RAG documentale è uno strato aggiuntivo, non alternativo.

Sequenza logica:

1. Athena riceve prompt e contesto documentale della conversazione.
2. Athena invoca n8n/Supabase pgvector per recuperare chunk dai documenti spot selezionati dall'utente.
3. Athena arricchisce il prompt con quei chunk.
4. Athena passa il prompt arricchito al normale flusso Athena.
5. Il flusso Athena mantiene filtro etico, configurazioni, guardrail e logiche già previste.
6. Se l'utente ha attivato il RAG generale, il flusso Athena può usare anche Weaviate e i documenti già contenuti nel vector database Athena.
7. La risposta finale può quindi combinare evidenza dai documenti spot e dal patrimonio documentale generale Athena.

Se l'utente non attiva il RAG generale, il mini-RAG documentale resta comunque disponibile per i documenti selezionati nella conversazione, mentre il retrieval Weaviate generale non viene usato.

## Ruolo di Supabase pgvector

Supabase pgvector è il vector store scelto per questa funzionalità.

Viene usato per:

- salvare chunk e embedding;
- fare similarity search rispetto al prompt;
- supportare indici temporanei legati a una sessione di lavoro;
- supportare cache personali persistenti, quando l'utente sceglie "Salva per riuso".

Non si introduce un vector database aggiuntivo dedicato. Non si usa n8n Simple Vector Store come architettura di produzione.

## Ruolo di Cohere

Cohere è il provider di embedding previsto.

La progettazione deve comunque mantenere un confine provider, così i test possono usare embedding fake o deterministici e il codice non dipende da Cohere in ogni punto.

## Ruolo di Microsoft 365

Microsoft 365 entra nella fase avanzata del progetto.

L'obiettivo finale è supportare:

- OneDrive personale;
- documenti condivisi;
- SharePoint e librerie Teams;
- identificazione stabile dei file tramite `driveId`, `itemId` ed `etag`.

Il Microsoft File Picker viene usato nel frontend per la selezione, ma i primi step backend devono funzionare senza File Picker e senza Graph reale.

## Cache personale persistente

Il primo uso dei documenti è temporaneo e legato alla conversazione. La temporaneità non significa "solo primo prompt": significa che il contesto documentale resta valido per l'intera conversazione, ma non sopravvive automaticamente a una nuova conversazione se l'utente non lo salva.

Dopo la prima risposta, Athena può mostrare un controllo "Salva per riuso". Se l'utente salva, il sistema conserva i metadati e gli embedding per evitare re-ingestion e re-embedding futuri.

La cache persistente è personale:

- appartiene all'utente;
- non è condivisa con altri;
- deve essere visibile in un pannello profilo/impostazioni;
- deve poter essere cancellata dall'utente;
- deve rilevare documenti stale tramite cambio di `etag`;
- deve aggiornarsi in modo lazy quando l'utente usa un documento cambiato.

## Durata del contesto mini-RAG documentale

Il contesto mini-RAG documentale è scoped alla conversazione.

Regole di base:

- la prima selezione di documenti crea il contesto documentale della conversazione;
- ogni prompt della stessa conversazione usa quel contesto;
- se l'utente aggiunge documenti, il contesto della conversazione si estende;
- il contesto viene resettato quando l'utente apre o crea una nuova conversazione;
- la cache persistente, se salvata, permette di riusare documenti in conversazioni future, ma non rende automaticamente globale il contesto della chat.

## Sequenza di sviluppo

Lo sviluppo deve procedere lentamente, con step quasi mono-funzionali.

La sequenza parte dal nucleo più piccolo:

`prompt + testo grezzo -> chunk rilevanti`

Poi aggiunge progressivamente:

1. documento singolo;
2. documenti multipli;
3. confine provider embedding;
4. Supabase pgvector;
5. n8n come workflow invocabile;
6. descrittori documento;
7. provider Microsoft 365;
8. cache personale persistente;
9. integrazione con chat Athena.

Ogni PRD deve essere leggibile insieme al quadro generale e ai PRD precedenti, così chi pianifica o implementa uno step sa quali capacità sono già state costruite e quali sono ancora fuori scope.

## Filosofia di sviluppo e validazione

Lo sviluppo deve seguire una filosofia TDD.

Per ogni PRD:

- i test devono essere scritti prima o insieme al codice applicativo;
- il codice deve includere wrapper o harness di test invocabili autonomamente;
- l'harness deve simulare l'input reale atteso in produzione nel modo più fedele possibile per quello step;
- ogni step deve usare e includere il codice dello step precedente;
- il codice precedente non deve essere riscritto se non per adattamenti di interfaccia, piccoli miglioramenti o correzioni emerse dai test;
- ogni comportamento ambiguo deve avere condizioni di validazione esplicite;
- quando la validazione richiede giudizio semantico, il test può usare una valutazione assistita da LLM, ma il criterio deve essere dichiarato in modo chiaro.

La progressione dei test deve avvicinarsi gradualmente alla condizione finale:

1. input raw minimale;
2. fixture testuali controllate;
3. documenti singoli;
4. documenti multipli;
5. embedding fake e reali;
6. pgvector;
7. workflow n8n;
8. descrittori documento;
9. provider Microsoft 365;
10. integrazione Athena.

Ogni harness deve produrre output JSON ispezionabile, log essenziali e almeno un caso positivo, un caso negativo e un caso limite.
