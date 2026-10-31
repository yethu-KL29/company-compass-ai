# Attoforce assistant: architecture diagrams

These charts describe the implemented cloud-mode architecture. The catalog is
synthetic; local-mode storage substitutes are omitted for readability. No web
search, clustering service, DRIFT search or separate recommendation engine is present.

## 1. System architecture

Both pages reuse the same chat implementation. Admin writes use authenticated API
endpoints, separate from the agent's read-only tools.

```mermaid
flowchart LR
  subgraph Browser[React and TypeScript]
    Public[Public page /] --> Chat[Shared Chat and useChat]
    Admin[Admin workspace /admin] --> Chat
    Admin --> Editors[Documents and Products editors]
  end
  subgraph Backend[Python FastAPI]
    ChatAPI[Chat API and SSE stream] --> Workflow[Single LangGraph agent]
    Workflow --> RAG[Local company_rag tool]
    Workflow --> MCPClient[MultiServerMCPClient native tools]
    Workflow --> Search[catalog_search: embed requirement text]
    Search --> MCPClient
    AdminAPI[Admin token validation] --> Knowledge[Knowledge ingestion service]
    AdminAPI --> Catalog[Catalog service and repository]
    Knowledge --> Manifest[Local document manifest]
    RAG --> Manifest
  end
  Chat -->|Message and optional thread ID| ChatAPI
  ChatAPI -->|SSE tokens and final answer| Chat
  Editors -->|Token and expected revision| AdminAPI
  Workflow <-->|Model calls and streaming| Gemini[Google Gemini on Vertex AI]
  RAG --> Embedding[Google embeddings: 1536 dimensions]
  Search --> Embedding
  Knowledge --> Embedding
  RAG <-->|BM25 and vector hybrid retrieval| Weaviate[(Weaviate)]
  Knowledge -->|Stage and replace document versions| Weaviate
  MCPClient <-->|MCP over stdio| MCP[Official Neo4j MCP server: read-only]
  MCP <-->|Schema and parameterized Cypher| Neo4j[(Neo4j Aura)]
  Catalog -->|Admin publication| Neo4j
  ChatAPI -. Request trace .-> Langfuse[Langfuse]
  Workflow -. Model and tool callbacks .-> Langfuse
```

Code: [page selection](../frontend/src/Application.tsx),
[workflow](../src/company_compass/agents/workflow.py),
[services](../src/company_compass/services),
[integrations](../src/company_compass/integrations).

## 2. Agent orchestration and memory

The model chooses tools using the system prompt and schema guidance. The four
callable functions come from two integrations: company RAG and Neo4j MCP.

```mermaid
flowchart TD
  Start([Message and thread ID]) --> Load[Load process-local thread state]
  Load --> Compact[Compaction node checks approximate token budget]
  Compact --> Needed{Over budget?}
  Needed -->|Yes| Summary[Unbound model summarizes older complete turns]
  Summary --> Replace[Keep bounded summary and recent complete turns]
  Needed -->|No| Agent
  Replace --> Agent[Gemini: prompt, schema guidance, summary and messages]
  Agent --> Decision{Native tool calls?}
  Decision -->|Yes| Tools[LangGraph ToolNode executes selected calls]
  Tools --> RAG[company_rag]
  Tools --> Schema[Neo4j get-schema]
  Tools --> Cypher[Neo4j read-cypher]
  Tools --> Search[catalog_search: hybrid top five and graph expansion]
  Search --> Result
  RAG --> Result[Append native tool results]
  Schema --> Result
  Cypher --> Result
  Result --> Agent
  Decision -->|No| Done([Complete answer])
  Agent -. Public text chunks .-> Stream[SSE stream]
  Load -. Thread state .-> Memory[(InMemorySaver)]
  Done -. Completed state .-> Memory
```

There is no fixed intent router or mandatory product preload. The graph has a
recursion limit; same-thread turns are serialized. Memory resets on backend
restart. Internal summary output is not streamed. Failed/cancelled turns restore
the preceding completed state. See [memory details](implementation-architecture.md#memory-and-compaction).

## 3. Streaming recommendation sequence

This is an example of model-selected calls, not a mandatory tool order. The agent
can clarify requirements, skip tools, or call either integration repeatedly.

```mermaid
sequenceDiagram
  actor User
  participant Chat as Shared chat UI
  participant API as FastAPI chat stream
  participant Graph as LangGraph workflow
  participant Model as Gemini
  participant RAG as company_rag
  participant Search as catalog_search
  participant MCP as Neo4j MCP
  participant DB as Neo4j Aura
  User->>Chat: Requirements, team size, budget and features
  Chat->>API: POST /api/chat/stream with message and optional thread_id
  API-->>Chat: session event with thread_id
  API->>Graph: Run with thread state and trace callbacks
  Graph->>Graph: Compact history if needed
  Graph->>Model: Prompt, conversation and tools
  opt Product discovery is needed
    Model-->>Graph: Call catalog_search with requirement text
    Graph->>Search: Embed requirement and prepare hybrid query
    Search->>MCP: Native read-cypher with vector and lexical terms
    MCP->>DB: Fuse search ranks and expand five products
    DB-->>MCP: Current products and fixed relationships
    MCP-->>Search: Search results
    Search-->>Graph: Product evidence without embedding arrays
    Graph->>Model: Tool result
  end
  opt Company context is needed
    Model-->>Graph: Call company_rag
    Graph->>RAG: Search documents
    RAG-->>Graph: Active-version evidence and sources
    Graph->>Model: Tool result
  end
  opt Catalog evidence is needed
    Model-->>Graph: Call get-schema or read-cypher
    Graph->>MCP: Execute native MCP tool arguments
    MCP->>DB: Read schema or bounded query
    DB-->>MCP: Catalog facts
    MCP-->>Graph: Native tool result
    Graph->>Model: Tool result
  end
  Model-->>Graph: Stream recommendation and tradeoffs
  Graph-->>API: Public text chunks
  API-->>Chat: token events as output arrives
  API-->>Chat: done with answer, sources, warnings and optional trace_id
  Chat-->>User: Markdown answer and source links
```

The browser sends only the next message and thread ID. Minimizing keeps Chat
mounted; New chat cancels the active request and resets client state. Full-page
navigation starts a fresh client conversation. Errors retain partial output and
display an error. Compaction is internal; only public model text is streamed.

## 4. Human-maintained document pipeline

The document ID survives replacement. The manifest determines which indexed
content version retrieval can use. Publication is synchronous and single-host.

```mermaid
flowchart TD
  Input[Upload file or edit title and content] --> Auth[Authenticate admin and validate input]
  Auth --> Lock[Acquire manifest lock and check expected revision]
  Lock --> Conflict{Stale revision?}
  Conflict -->|Yes| Reject[HTTP 409: keep browser draft]
  Conflict -->|No| Hash[Build content version and chunks]
  Hash --> Same{Content unchanged?}
  Same -->|Yes| Existing[Return existing publication without embedding]
  Same -->|No| Embed[Embed chunks: gemini-embedding-001, 1536 dimensions]
  Embed --> Stage[Stage versioned chunks in Weaviate]
  Stage --> Success{Indexing succeeded?}
  Success -->|No| Failure[Keep previous publication and return error]
  Success -->|Yes| Publish[Atomically publish manifest: same ID and next revision]
  Publish --> Active[Retrieval accepts only active manifest versions]
  Publish --> Clean[Clean superseded vectors]
  Clean --> Complete[Return publication and any cleanup warning]
```

Supported uploads are TXT, Markdown, text PDF and DOCX; OCR is not implemented.
Official URL refresh skips admin-edited documents. Failed cleanup cannot undo a
successful replacement. See [document management](document-management.md).

## 5. Human-maintained product publication

Admin publication uses the application's write connection, separate from read-only
MCP. Historical product revisions remain in Neo4j.

```mermaid
sequenceDiagram
  actor Admin
  participant UI as Products editor
  participant API as Admin API
  participant Service as Catalog service
  participant Repo as Catalog repository
  participant DB as Neo4j
  Admin->>UI: Edit product and plans in place
  UI->>API: Save with token and expected revision
  API->>API: Authenticate and validate
  API->>Service: Publish product
  Service->>Repo: Publish with expected revision
  Repo->>DB: Transaction checks revision and publishes
  alt Revision conflict
    DB-->>Repo: Reject stale publication
    Repo-->>API: Conflict
    API-->>UI: HTTP 409 with draft preserved
  else Successful publication
    DB->>DB: Add immutable revision, variants and facts
    DB->>DB: Preserve HAS_REVISION and move CURRENT_REVISION
    DB-->>Repo: Published product
    Repo-->>Service: Current publication
    Service-->>API: Published product
    API-->>UI: Saved revision
    UI-->>Admin: Updated product details
  end
```

## 6. Catalog graph for recommendations

These are Neo4j node labels and relationship types. Recommendations follow
`CURRENT_REVISION`; `HAS_REVISION` also reaches historical publications.

```mermaid
flowchart LR
  Company[Company] -->|HAS_CATALOG| Catalog
  Catalog[Catalog] -->|HAS_PRODUCT| Product[Product]
  Product -->|CURRENT_REVISION| Current[ProductRevision: published]
  Product -->|HAS_REVISION| History[ProductRevision: historical or current]
  Current -->|IN_CATEGORY| Category[Category]
  Current -->|HAS_VARIANT| Plan[Variant: product plan]
  Plan -->|HAS_CAPABILITY| Capability[Capability]
  Plan -->|SUPPORTS| UseCase[UseCase]
  Plan -->|FOR_AUDIENCE| Audience[Audience]
  Plan -->|HAS_PRICE| Price[PriceOffer]
  Plan -->|HAS_ATTRIBUTE| Value[AttributeValue]
  Value -->|DEFINED_BY| Definition[AttributeDefinition]
  Plan -->|UPGRADES_TO| Upgrade[Variant: same product revision]
  Plan -->|COMPLEMENTS| Other[Product: resolve current revision]
  Current -->|SUPPORTED_BY| Source[Source: synthetic provenance]
  Change[ChangeEvent: publication audit] -->|CHANGED| Product
  Change -->|RESULTED_IN| Current
```

Catalog discovery embeds descriptions/use cases and fuses vector/full-text ranks
into five current products with relationship context. See the [hybrid pipeline](catalog-hybrid-search.md).
The model queries task fit, included capabilities, capacity and comparable price
units, then explains evidence and tradeoffs. Similarity comes from shared facts,
not a stored SIMILAR_TO relationship. Prices use integer minor units; unknown
mandatory attributes cannot establish eligibility. See [query schema](knowledge/catalog/schema.md)
and [Neo4j guide](neo4j-guide.md).

## 7. Observability structure

Each HTTP turn creates one trace. Turns in a conversation share a Langfuse session
ID. Native framework callbacks attach under the request observation.

```mermaid
flowchart TD
  Session[Conversation: session_id equals thread_id] -. Groups turns .-> Request[Request trace: company-compass-chat]
  Request --> Workflow[company-compass-workflow callback span]
  Workflow --> Compact[compact node]
  Compact --> Summary[Gemini summary generation, if needed]
  Workflow --> Agent[agent node]
  Agent --> Generation[Gemini generation: usage and latency]
  Workflow --> Tools[tools node, if selected]
  Tools --> RAG[company_rag observation]
  Tools --> MCP[Native Neo4j tool observation]
  Tools --> Search[catalog_search observation]
```

Trace names retain the internal project identifier. Visible chat branding is
**Attoforce assistant**. Content export follows configured masking; credentials
and internal reasoning are excluded from public output. See [observability code](../src/company_compass/integrations/observability.py).
