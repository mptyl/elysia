# Piano di Implementazione: Web Search via OpenRouter `:online`

**Stato**: Pianificato (non implementato)
**Data**: 2026-03-18

## Contesto

Atena attualmente chiama i modelli LLM tramite OpenRouter come pura chat completion. Il modello risponde solo per inferenza interna + contesto RAG da Weaviate. Non consulta mai il web.

L'obiettivo e' dare al sistema la possibilita' di cercare sul web quando serve: informazioni in tempo reale, fatti oltre il knowledge cutoff, notizie, dati aggiornati, ecc.

### Perche' OpenRouter `:online`

OpenRouter **non** supporta il passthrough del grounding nativo di Gemini (`google_search`). Offre pero' il suffisso `:online` (es. `google/gemini-3.1-pro-preview:online`) che aggiunge una ricerca web via [Exa.ai](https://exa.ai) prima di ogni chiamata al modello.

Caratteristiche chiave:
- **Funziona con tutti i modelli** su OpenRouter (Gemini, Claude, GPT, Mistral, ecc.) perche' la ricerca e' gestita da OpenRouter stesso, non dal provider del modello
- La ricerca viene **sempre eseguita** quando il suffisso e' presente (non e' il modello a decidere)
- Costo aggiuntivo: ~$0.004/richiesta (Exa a $4/1000 risultati, default 5 risultati)
- Le risposte includono annotazioni `url_citation` con link alle fonti

### Impatto sulle chiamate LLM

L'implementazione **non aggiunge chiamate LLM extra**:

1. Il **DecisionNode** (gia' esistente) sceglie quale tool usare — aggiungere `WebSearchAnswer` come opzione non aggiunge una chiamata, ma solo un'opzione in piu' nella scelta
2. **WebSearchAnswer** fa 1 sola chiamata LLM (meno di DirectAnswer che ne fa 2: classificatore + risposta)
3. OpenRouter esegue la ricerca Exa *prima* di inoltrare il prompt al modello, iniettando i risultati nel contesto — tutto in una singola chiamata API

## Approccio: Nuovo Tool `WebSearchAnswer`

Creare un nuovo tool nel decision tree che usa la variante `:online` del modello. Il decision node (LLM) decide autonomamente quando instradare la query verso questo tool, basandosi sulla sua descrizione.

**Perche' un tool separato e non modificare DirectAnswer**: il suffisso `:online` esegue SEMPRE la ricerca web. Mettendolo in un tool dedicato, la ricerca scatta solo quando il decision node lo sceglie, evitando costi inutili per chitchat o query risolvibili via RAG.

## Modifiche Necessarie

### 1. Nuovo file: `elysia/tools/text/web_answer.py`

Nuovo tool `WebSearchAnswer`, seguendo il pattern di `DirectAnswer` (`elysia/tools/text/direct_answer.py`):

```python
import dspy
from elysia.objects import Response, Tool
from elysia.tree.objects import TreeData
from elysia.util.client import ClientManager
from elysia.util.elysia_chain_of_thought import ElysiaChainOfThought
from elysia.tools.text.prompt_templates import WebSearchResponsePrompt


def _create_online_lm(lm: dspy.LM) -> dspy.LM:
    """
    Create a copy of the given LM with ':online' appended to the model name.
    Only works with OpenRouter models (model name starts with 'openrouter/').
    """
    model_name = lm.model  # e.g. "openrouter/google/gemini-3.1-pro-preview"
    online_model_name = f"{model_name}:online"
    return dspy.LM(
        model=online_model_name,
        api_base=lm.api_base,
        max_tokens=lm.kwargs.get("max_tokens", 8000),
    )


class WebSearchAnswer(Tool):
    def __init__(self, **kwargs):
        super().__init__(
            name="web_search_answer",
            description="""
            Answer the user's question using real-time web search.
            Use this tool when:
            - The user asks about current events, news, or real-time data.
            - The question requires information beyond the knowledge cutoff date.
            - The user explicitly asks to search the web.
            - The answer requires up-to-date facts (prices, scores, weather, statistics, etc.).
            Do NOT use this for questions answerable from the document collection or general knowledge.
            """,
            status="Searching the web...",
            inputs={},
            end=True,
        )

    async def is_tool_available(
        self,
        tree_data: TreeData,
        base_lm: dspy.LM,
        complex_lm: dspy.LM,
        client_manager: ClientManager | None = None,
        **kwargs,
    ):
        """Web search is disabled or the provider does not support it."""
        return tree_data.web_search_enabled

    async def __call__(
        self,
        tree_data: TreeData,
        inputs: dict,
        base_lm: dspy.LM,
        complex_lm: dspy.LM,
        client_manager: ClientManager | None = None,
        **kwargs,
    ):
        online_lm = _create_online_lm(complex_lm)

        text_response_generator = ElysiaChainOfThought(
            WebSearchResponsePrompt,
            tree_data=tree_data,
            environment=False,
            tasks_completed=True,
            message_update=False,
            profile_context=bool(tree_data.profile_system_prompt),
        )

        output = await text_response_generator.aforward(lm=online_lm)
        yield Response(text=output.response)
```

### 2. `elysia/tools/text/prompt_templates.py`

Aggiungere `WebSearchResponsePrompt` — signature DSPy simile a `TextResponsePrompt` ma con istruzione specifica:

```python
class WebSearchResponsePrompt(dspy.Signature):
    """You are answering the user's question using information retrieved from the web.
    Provide a clear, accurate response based on the web search results.
    Always cite your sources when referencing specific facts or data from the web.
    If the web results don't contain sufficient information, state this clearly."""

    user_prompt: str = dspy.InputField(desc="The user's question")
    response: str = dspy.OutputField(desc="Your response based on web search results")
```

### 3. `elysia/tree/objects.py` — TreeData

Aggiungere campo:

```python
web_search_enabled: bool = False
```

### 4. `elysia/config.py` — Settings

Nella classe `Settings`, in `base_init()`:

```python
self.ENABLE_WEB_SEARCH: bool = False
```

In `set_from_env()`:

```python
self.ENABLE_WEB_SEARCH = os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"
```

Nella validazione, verificare che il provider sia OpenRouter quando web search e' abilitato:

```python
if self.ENABLE_WEB_SEARCH:
    is_openrouter = (
        (self.BASE_PROVIDER and self.BASE_PROVIDER.startswith("openrouter"))
        or (self.COMPLEX_PROVIDER and self.COMPLEX_PROVIDER.startswith("openrouter"))
    )
    if not is_openrouter:
        logger.warning("ENABLE_WEB_SEARCH=true but provider is not OpenRouter. Web search tool will be unavailable.")
```

### 5. `elysia/tree/tree.py` — Registrazione tool

Import:

```python
from elysia.tools.text.web_answer import WebSearchAnswer
```

In `multi_branch_init()` e `one_branch_init()`, dopo `DirectAnswer`:

```python
self.add_tool(branch_id="base", tool=WebSearchAnswer)
```

Passare `web_search_enabled` da Settings a TreeData. Cercare dove `TreeData` viene inizializzato e aggiungere:

```python
tree_data.web_search_enabled = settings.ENABLE_WEB_SEARCH
```

### 6. `elysia/.env.example`

Aggiungere:

```bash
# Web Search (OpenRouter :online suffix - uses Exa.ai, ~$0.004/request)
# Works with all models on OpenRouter (Gemini, Claude, GPT, Mistral, etc.)
# ENABLE_WEB_SEARCH=false
```

## Limitazioni

| Limitazione | Dettaglio |
|---|---|
| Solo OpenRouter | Il suffisso `:online` e' specifico di OpenRouter. Con provider diretti (Gemini API, OpenAI API) il tool non e' disponibile. Funziona pero' con qualsiasi modello su OpenRouter |
| Exa.ai, non Google Search | Qualita' buona ma non identica a Google Search nativo |
| Costo aggiuntivo | ~$0.004/richiesta extra per la ricerca Exa |
| Ricerca sempre attiva | Quando il tool viene scelto, la ricerca scatta sempre. E' il decision node a decidere *se* usare il tool, non il modello a decidere *se* cercare |
| Nessun controllo granulare | Non si possono filtrare domini, limitare risultati ecc. (per quello servirebbe il parametro `plugins` invece del suffisso `:online`) |

## Verifica

### Unit test (`tests/no_reqs/general/test_web_answer.py`)

- `is_tool_available()` restituisce `False` quando `web_search_enabled=False`
- `is_tool_available()` restituisce `True` quando `web_search_enabled=True`
- `_create_online_lm()` appende correttamente `:online` al model name
- Il model name risultante e' corretto (es. `openrouter/google/gemini-3.1-pro-preview:online`)

### Test manuale end-to-end

1. Settare `ENABLE_WEB_SEARCH=true` nel `.env`
2. Avviare il backend (`elysia start`)
3. Connettersi via frontend
4. Verificare routing:
   - "Qual e' il tasso di cambio EUR/USD oggi?" → `web_search_answer`
   - "Ciao come stai?" → `direct_answer` (non web search)
   - "Cosa dice il documento X?" → `query` (RAG)
5. Verificare che la risposta web contenga informazioni aggiornate e citazioni

## Evoluzione futura

- **Plugin mode**: sostituire il suffisso `:online` con il parametro `plugins` per avere controllo granulare (max risultati, filtro domini, scelta engine)
- **Gemini nativo**: se si passa al provider Gemini diretto, implementare il grounding nativo (`tools=[{"google_search": {}}]`) dove il modello decide autonomamente quando cercare
- **Citazioni strutturate**: parsare le annotazioni `url_citation` di OpenRouter e presentarle come citazioni cliccabili nel frontend
