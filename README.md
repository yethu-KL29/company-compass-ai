# Company Compass

A Python/LangGraph company assistant using Gemini, Weaviate hybrid RAG and the official Neo4j MCP server. The catalog contains20 fictional software products and39 plans for the assignment.

The user message goes directly to one tool-calling agent. It receives one unified tool list:
Neo4j MCP `get-schema`/`read-cypher`, local `company_rag`, and `catalog_search`
which embeds requirement text and runs Neo4j hybrid search through native MCP.
Its system prompt and graph schema guide tool choice;
results return to the same agent for further calls or a streamed answer.
Async startup discovers the native MCP tools with MultiServerMCPClient.get_tools(),
merges them with the RAG tool, then builds the workflow once.

## Run

```powershell
uv sync --extra dev --extra neo4j-mcp
# Copy .env.example to .env and supply your own credentials.
cd frontend
npm ci
cd ..
./scripts/start-dev.ps1
```

Open http://127.0.0.1:5173 for the public assistant, or
http://127.0.0.1:5173/admin for the existing administration workspace.
The launcher starts missing backend/frontend services in
hidden processes and writes logs under ignored `data/runtime/`. Restart the backend
after Python/configuration changes. Never commit `.env` or service-account JSON.

Use `uv run company-compass check` for storage readiness. `seed` adds missing demo
products while preserving edits. `ingest https://attoforce.ai/` ingests an official
company page. `mcp-check` verifies configured Neo4j MCP schema/read operations.

Set `NEO4J_MCP_COMMAND` to the installed `neo4j-mcp` executable and
`NEO4J_MCP_ARGS=[]`. The server receives Neo4j credentials from settings and runs
read-only. Gemini uses Vertex service-account/ADC authentication by default and
medium reasoning. Company embeddings use `gemini-embedding-001`,1536 dimensions;
existing collections require migration before changing vector settings.

## Interface

- **Assistant:** streamed answers, recommendations and comparisons in chat. New chat
  starts a fresh in-memory thread. Switching sections preserves the current thread.
- **Documents:** view IDs/titles/full content; admins upload TXT/MD/PDF/DOCX or edit
  and re-ingest an existing document with its identity preserved.
- **Products:** use Edit on a product card or detail to edit it in place. Save changes
  publishes a new revision; Cancel discards the draft. Add product opens a blank form.

Admin writes require the configured token. Chat tools cannot publish changes.

## Code

```text
src/company_compass/
  main.py                 FastAPI application factory
  cli.py                  Run/check/seed/ingest commands
  agents/
    workflow.py           LangGraph agent/tool loop
    assistant.py          Thread ownership and stream events
    memory.py             Conversation summarization/compaction
    system_prompt.md      Agent instructions
  api/                    Routes, dependencies, safe errors
  core/                   Settings and service wiring
  models/                 Request, graph-state and catalog contracts
  integrations/           Gemini, two agent tools, MCP, embeddings/Weaviate
  repositories/           Catalog persistence and revision publication
  services/               Admin catalog and document ingestion/retrieval
  utils/                  Upload extraction, document metadata, atomic storage
frontend/src/
  features/               Assistant, Documents and Products
  services/               HTTP/SSE client
  models/                 UI contracts
  components/             Shared UI
```

## Checks and documentation

```powershell
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
cd frontend
npm test
npm run build
npm run format:check
```

See [architecture](docs/implementation-architecture.md),
[Mermaid diagrams](docs/architecture-diagrams.md),
[requirements](docs/requirements.md), [graph schema](docs/knowledge/catalog/schema.md),
[document management](docs/document-management.md) and [verification](docs/verification.md).

Conversation memory is process-local and resets on backend restart. It is compacted
into a bounded summary plus recent complete turns. Web search is removed. There is
no fixed intent router, separate ranking engine or persistent conversation database.

Catalog discovery uses vector/full-text reciprocal rank fusion and returns five
current products with graph relationships. Run `uv run company-compass index-catalog`
once to create indexes and embed existing products. Admin saves keep embeddings in
sync. See [catalog hybrid search](docs/catalog-hybrid-search.md).

## Langfuse observability

The official [Langfuse skill](https://github.com/langfuse/skills/tree/main/skills/langfuse)
was installed and used for this integration. Langfuse Python SDK5.1 uses its native
LangChain callback to trace the existing LangGraph workflow without adding agents
or tools. Each chat turn has one trace; conversation thread IDs group turns into
sessions. Model calls, tool inputs/results, compaction, latency and provider usage
are nested beneath the request. Costs shown by Langfuse are model-price estimates.

Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL in ignored .env.
LANGFUSE_ENABLED=false disables tracing. LANGFUSE_CAPTURE_CONTENT defaults to false
(metadata only); the supplied local demo configuration enables sanitized content
for debugging public/synthetic data. Known credential values, credential-shaped
fields, email addresses, private keys and reasoning/signature blocks are redacted
before export. This is not comprehensive classification of confidential documents.

No credentials go to the frontend. A tracing failure does not retry paid inference
or block chat. Shutdown flushes pending observations. Live verification fetches
observations via the current Langfuse CLI API; SDK calls alone are not delivery proof.

Assistant Markdown supports headings, emphasis, lists, code, links and GFM tables
while streaming. Raw HTML and remote image loading are disabled; user messages stay
literal text.

For a full walkthrough of the actual graph,see [understanding Neo4j](docs/neo4j-guide.md).
