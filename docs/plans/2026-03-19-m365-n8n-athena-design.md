# Microsoft 365, n8n, and AthenaAI Design Notes

> Status: brainstorming/design note
>
> Purpose: preserve the current discussion so it can be resumed later without rereading the full chat.

## Objective

Define a practical first version for letting an AthenaAI user access their Microsoft 365 documents through n8n and Microsoft Graph, then use the retrieved content inside AthenaAI/Elysia with an external LLM.

The design target discussed so far is:

- live retrieval rather than full sync/indexing
- access to both OneDrive and SharePoint
- n8n as the primary gateway to Microsoft Graph
- an intermediate check before full document extraction
- support for both conversational use and controlled document-editing workflows

## Technical Context Observed in Elysia

The current AthenaAI/Elysia codebase already contains some relevant building blocks, but not yet the target document workflow:

- [static_frontend.py](/Users/mp/athenaAI/elysia/elysia/api/routes/static_frontend.py) already contains Microsoft Graph token handling and directory/profile sync logic. This appears to be used for directory-style lookups rather than Office/SharePoint file access.
- [query.py](/Users/mp/athenaAI/elysia/elysia/api/routes/query.py) shows that the main user interaction path is a WebSocket query pipeline.
- [collections.py](/Users/mp/athenaAI/elysia/elysia/api/routes/collections.py) confirms the current retrieval model is oriented around internal collections rather than live Microsoft 365 browsing.
- [MULTI_TENANT_PLAN.md](/Users/mp/athenaAI/elysia/MULTI_TENANT_PLAN.md) shows active work on authentication and tenant isolation, which is relevant because document access must remain scoped to the authenticated user and organization.

Conclusion: AthenaAI is not starting from zero on auth/Azure integration, but Microsoft 365 document access should still be treated as a new product capability rather than a small extension of the current Graph usage.

## Decision Taken So Far

The chosen direction is `approach 1`: use `n8n` as the main gateway for Microsoft 365 access.

This means:

- AthenaAI/Elysia does not directly orchestrate Microsoft Graph document retrieval in v1.
- n8n handles OAuth, token lifecycle, Graph calls, document discovery, download, and first-pass extraction.
- AthenaAI sends a structured request to n8n and consumes the returned file metadata, snippets, or extracted content.

This boundary keeps Microsoft-specific complexity outside the core Elysia app and makes n8n the enforcement point for access, retrieval, and workflow control.

## Recommended v1 Flow

The agreed interaction model is:

1. The user asks AthenaAI to search or use their Microsoft 365 documents.
2. AthenaAI sends a structured request to n8n with the user context, query, requested scope, and operational limits.
3. n8n searches OneDrive and/or SharePoint through Microsoft Graph.
4. n8n returns candidate files first, not full documents.
5. AthenaAI performs an intermediate check with the user or with product logic.
6. Only selected documents are fetched and extracted in full.
7. AthenaAI sends the selected content to the external LLM.

Short form:

`search -> intermediate check -> fetch/extract -> LLM`

This avoids the worst default behavior: sending full documents to an external LLM just because a search matched.

## Data Policy

The current policy direction is:

- first pass: return metadata and small snippets/previews
- second pass: fetch and extract full content only when necessary
- full documents may be used, but not as the default behavior

This balances usability with cost, latency, and data minimization.

Recommended minimum controls for v1:

- max number of documents per request
- max total extracted text size before LLM submission
- audit log of who requested access and which files were fetched
- clear provenance in AthenaAI responses

## What the Documents Can Be Used For

The discussion clarified that Microsoft 365 documents are useful for more than retrieval-only chat. The main product uses identified so far are:

- Q&A over user documents
- summarization, extraction, and synthesis
- conversational grounding inside AthenaAI
- drafting or proposing document changes

The important product distinction is between `read` and `write`.

Recommended v1 posture:

- reading and interpretation are first-class
- document modification is allowed as a proposed output
- direct saving back to Microsoft 365 should not be autonomous by default

Safer write flow:

1. AthenaAI retrieves the relevant content through n8n.
2. The external LLM proposes edits, rewrites, or a new draft.
3. The user reviews and approves.
4. n8n saves a new version or updates the target file.

This makes AthenaAI a copilot/editor assistant rather than an unsupervised document mutator.

## Microsoft 365 Business vs Microsoft 365 Copilot

An important clarification from the discussion: "Microsoft 365 Pro" is not a precise product name, so the real distinction is between standard Microsoft 365 business licensing and the separate `Microsoft 365 Copilot` add-on.

Working assumption for future design:

- if the customer only has standard Microsoft 365 business licensing, AthenaAI should rely on `n8n + Graph` for document access and treat Microsoft Copilot as a separate end-user experience
- if the customer has `Microsoft 365 Copilot`, then deeper product integration may become worthwhile, because Copilot can be part of the architecture rather than just a neighboring tool

Practical implication:

- without `Microsoft 365 Copilot`, AthenaAI remains the main orchestrator
- with `Microsoft 365 Copilot`, AthenaAI may eventually hand off part of the experience to the Microsoft ecosystem more natively

## Open Questions to Resume Later

The discussion should continue from these unresolved product questions:

- Which concrete v1 use cases matter most: Q&A, summary/report generation, or document rewrite/redline?
- What exactly should AthenaAI send to n8n as the request schema?
- How should the intermediate check appear in the UX: automatic ranking, explicit user confirmation, or both?
- Which file types must be supported in v1: Word, Excel, PowerPoint, PDF, plain text?
- Should saves always create a new document/version, or can approved changes overwrite an existing file?
- What should happen when a tenant has Microsoft 365 Copilot available for some users but not others?
- When should AthenaAI hand off to Copilot-style in-app editing versus finishing the task itself?

## Current Recommendation Snapshot

If work resumes later, the current recommended baseline is:

- n8n as the Microsoft 365 gateway
- live retrieval, not full sync
- OneDrive + SharePoint scope
- intermediate `search first, fetch second` workflow
- default to metadata/snippets first
- allow full document use only when needed
- support proposed edits with human approval before save

This note is intentionally not a final spec. It is the checkpoint needed to restart the design discussion efficiently.
