# Athena Customizations (Backend)

This document tracks all divergences from the upstream `weaviate/elysia` repository.

## Configuration & Models
- **File**: `elysia/config.py`
- **Change**: Added support for Gemini 3.0 Flash/Pro Preview, Gemini 2.5, and adjusted provider mappings for Google/OpenRouter.
- **Reason**: Enable experimental Gemini models not yet in upstream.

## Core Logic
- **File**: `elysia/tree/util.py`
- **Change**: Implemented RAG bypass mechanism (`direct_answer`), added ethical guardrails, and fixed the "double response" bug by preventing redundant message updates.
- **File**: `elysia/tools/text/direct_answer.py`
- **Change**: [NEW] Tool to handle direct answers avoiding RAG when appropriate.
- **File**: `elysia/tools/text/prompt_templates.py`
- **Change**: Updated templates to include ethical guidelines and style instructions.

## API & Services
- **Files**: `elysia/api/routes/*`, `elysia/api/services/tree.py`
- **Change**: Adjusted to support the new `direct_answer` tool and ethical parameters.

## Testing
- **File**: `tests/no_reqs/general/test_rag_bypass_nr.py`
- **Change**: [NEW] Tests for the RAG bypass functionality.

## Tools & Data
- **Change**: [NEW] script to batch upload PDFs to Weaviate with custom embedding support (Cohere).
- **File**: `weaviate/import/import_jeopardy_question.py`
- **Change**: script for importing jeopardy questions.
- **File**: `elysia/api/custom_tools.py`
- **Change**: Includes `TellAJoke` tool and imports for `BasicLinearRegression`.

## Knowledge & Specs (Root Level)
- **Folder**: `openspec/`
- **Change**: [NEW] Cross-project specifications and agent conventions.
- **Folder**: `project_design/`
- **Change**: [NEW] Architecture analysis and implementation plans.

## Upstream Synchronization Risks

> **CRITICAL**: This fork modifies core logic files. Expect merge conflicts during `git pull upstream main`.

### High Risk Files (Manual Resolution Likely Required)
1. **`elysia/config.py`**:
   - **Risk**: High. We inject custom providers (Gemini, OpenRouter) into `provider_to_models` and `Settings`.
   - **Resolution**: preserve Athena's `provider_to_models` additions and `Settings` defaults while accepting upstream's new configurations.

2. **`elysia/tree/util.py`**:
   - **Risk**: High. We modified the `run_tree` logic to support `direct_answer` (RAG bypass).
   - **Resolution**: Ensure the bypass check remains at the start of the execution flow.

### Maintenance Protocol
- Always review this document before resolving conflicts.
- For `config.py`, verify if upstream added support for new models that might supersede our custom injections.
