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
- **File**: `weaviate/import/import_pdfs.py`
- **Change**: [NEW] script to batch upload PDFs to Weaviate with custom embedding support (Cohere).
