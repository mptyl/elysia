# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elysia is a **fork** of [weaviate/elysia](https://github.com/weaviate/elysia), customized for the Athena project. It's a decision-tree agentic RAG platform built with FastAPI, DSPy, and Weaviate. The fork adds Gemini model support, a RAG bypass mechanism (`DirectAnswer` tool), and ethical guardrails. See `CUSTOMIZATIONS.md` for all divergences from upstream.

## Commands

### Run the server
```bash
# From within the .venv
elysia start                    # default: localhost:8090
elysia start --port 8090 --host 0.0.0.0
```

### Install
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"         # editable install with dev deps
```

### Tests
```bash
pytest --ignore=tests/requires_env -v           # no-external-deps tests (CI default)
pytest tests/no_reqs/general/test_rag_bypass_nr.py -v   # single test file
pytest tests/no_reqs/api/ -v                    # API tests only
# tests/requires_env/ needs API keys + Weaviate cluster (costly LLM calls)
```

### Formatting
Uses **black** for Python formatting.

## Architecture

### Core Flow
1. **CLI** (`elysia/api/cli.py`) → starts uvicorn with `elysia/api/app.py`
2. **FastAPI app** (`elysia/api/app.py`) → mounts routes, serves static NextJS frontend, runs background schedulers (timeout checks, resource monitoring)
3. **WebSocket `/ws/query`** (`elysia/api/routes/query.py`) → main entry point for user queries. Streams results back in real-time via JSON payloads
4. **UserManager** (`elysia/api/services/user.py`) → manages per-user Trees and Weaviate clients
5. **Tree** (`elysia/tree/tree.py`) → the decision tree executor. Contains branches of `DecisionNode`s and `Tool`s. Iterates up to `recursion_limit` times per query
6. **DecisionNode** (`elysia/tree/util.py`) → LLM-powered node that picks which tool to execute next based on available options, environment context, and conversation history. Uses DSPy with assertion-based retry (`AssertedModule`)
7. **Tools** yield `Response`, `Result`, `Retrieval`, `Error` objects back through the tree → WebSocket → frontend

### Key Abstractions
- **`Settings`** (`elysia/config.py`): Dual-model config (BASE_MODEL for fast/cheap, COMPLEX_MODEL for hard tasks). Provider routing via litellm. Global `settings` singleton for package use; per-user settings via the API
- **`TreeData`** (`elysia/tree/objects.py`): Shared state across all agents in a tree run — user prompt, conversation history, environment (retrieved objects), tasks completed, errors
- **`Environment`** (`elysia/tree/objects.py`): Persistent store of all retrieved/generated objects, keyed by `tool_name → result_name → [{metadata, objects}]`. Visible to all agents for context awareness
- **`Tool`** (`elysia/objects.py`): Base class for all tools. Must implement async `__call__` as a generator (yield results). Has `is_tool_available()` and `run_if_true()` hooks. The `@tool` decorator can create tools from plain async functions
- **`ElysiaKeyManager`** (`elysia/config.py`): Context manager that temporarily swaps env vars to match per-user API key settings during LLM calls

### Built-in Tools
- **Query** / **Aggregate** (`elysia/tools/retrieval/`): Weaviate collection search and aggregation
- **CitedSummarizer** / **FakeTextResponse** (`elysia/tools/text/text.py`): Text generation with/without citations
- **DirectAnswer** (`elysia/tools/text/direct_answer.py`): [ATHENA-CUSTOM] Bypasses RAG for simple/conversational queries. Auto-selects base vs complex model based on prompt complexity
- **Visualise** / **BasicLinearRegression** (`elysia/tools/visualisation/`): Data visualization
- **SummariseItems** (`elysia/tools/postprocessing/`): Post-retrieval summarization
- Custom tools go in `elysia/api/custom_tools.py`

### API Routes (prefix → module)
`/init`, `/ws` (query + processor), `/collections`, `/user/config`, `/tree/config`, `/feedback`, `/util`, `/tools`, `/db`, `/api/health`

## Athena-Specific Changes (High Merge-Conflict Risk)
- `elysia/config.py`: Custom `provider_to_models` entries for Gemini 3/2.5 and OpenRouter. Look for `[ATHENA-CUSTOM]` markers
- `elysia/tree/util.py`: Modified decision node to handle `direct_answer` tool (no `message_update` for text responses)
- `elysia/tools/text/direct_answer.py`: New tool (not in upstream)

## Branching
- `main`: new features
- `release/vY.Z.x`: bugfixes for released versions
- Branch naming: `feature/`, `bugfix/`, `hotfix/`, `docs/`, `chore/` prefixes

## Environment Variables
Copy `.env.example` → `.env`. Key variables: `WCD_URL`, `WCD_API_KEY`, `OPENROUTER_API_KEY` (recommended), `BASE_MODEL`, `COMPLEX_MODEL`, `BASE_PROVIDER`, `COMPLEX_PROVIDER`. Smart setup auto-selects models based on available API keys.
