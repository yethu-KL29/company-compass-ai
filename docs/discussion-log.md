# Discussion log

## 2026-10-31 - Greenfield discovery

- User requested an AI assistant using a framework and MCP for company questions and requirement-based product recommendations.
- User requested brainstorming, research, planning, architecture, stack selection, and repository notes for future reference.
- Inspected the workspace: only `.git` existed; no existing application or repository instructions were found.
- Researched official framework, MCP, provider, storage, frontend, and IKEA India documentation. See [research](research.md).
- Proposed IKEA India, home-office products, English, INR, and a local-first MVP as provisional defaults. None were user-confirmed.
- Asked optional clarification about company preference, delivery level, evaluation/deadline, API budget, deployment, and live data. Answers remain pending.
- User clarified that their concern was whether the company would remain the same. The fixed-company assumption is now explicitly unresolved. Distinguish fixed, operator-configurable, customer-selectable, and arbitrary-company scope before final architecture.
- Saved a [provisional plan](plan.md), not an implemented application. No dependencies installed, paid API calls made, deployment created, or benchmarks run.
- Git status inspection required a command-scoped `safe.directory` exception because sandbox and workspace owners differ. No global Git configuration was changed.

## 2026-10-31 - Fixed company and daily knowledge ingestion

- User confirmed that the company is fixed, resolving the earlier scope question. Company identity remains undecided.
- User proposed a knowledge management system with hybrid RAG, an ingestion MCP server, and a daily pipeline to search recent company updates and automatically ingest changes.
- Adopted those directions in the draft. Proposed Firecrawl MCP for discovery/extraction, a separate scheduled worker, versioned publication, PostgreSQL lexical search plus pgvector, and catalog updates alongside document indexing. These implementation selections remain proposals.
- Verified that Perplexity documents background indexing and query-time fetching/synthesis; did not assert an undocumented internal vector database architecture.
- User asked whether product recommendations should be company-specific or arbitrary. Recommended interpreting the original company-assistant brief as the fixed company's offerings; recorded this as an interpretation rather than claiming the brief explicitly mandates it.
- Added [ingestion and retrieval design](ingestion-and-retrieval.md). Updated requirements and plan to remove current multi-company scope and supersede the snapshot-only ingestion assumption.
- The earlier delivery estimate needs revision for automated ingestion and knowledge management. No runtime schedule or paid service was activated.

## 2026-10-31 - Retrieval necessity discussion

- User asked whether hybrid retrieval is needed.
- Clarified the proposal: it is useful to evaluate for mixed conversational and exact-term queries, but neither a fixed company nor daily updates makes it mandatory.
- Proposed a vector-plus-metadata baseline and a comparison with lexical-plus-vector retrieval on identical evaluation cases. No benchmark or final retrieval selection has been made.
- Product identifiers use structured lookups and budget/specification constraints use catalog filters. Hybrid search cannot correct stale or missing source data.
- Updated current documentation to distinguish proposed hybrid retrieval from confirmed product scope.

## 2026-10-31 - Vector database necessity

- User clarified that their question concerns whether a vector database is needed.
- Clarified that RAG can use PostgreSQL full-text retrieval without embeddings, alongside structured catalog queries. Embeddings are optional; pgvector can add semantic retrieval without a separate database service.
- Hybrid lexical-plus-vector retrieval requires vector-search capability, but the assistant itself does not. No final storage or retrieval change was requested or made.
