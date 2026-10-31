# Discussion and decision log

## 2026-10-31 - Final user-directed orchestration

The user explicitly replaced the earlier fixed plan/retrieve/answer approach:
user message -> one agent -> model-selected RAG/Neo4j MCP tools -> same agent -> answer.
Exactly two tools; web search removed. Separate LangGraph workflow, streaming and
in-memory compaction are confirmed. No clarification was needed: the user corrected
"3tools" to "only these2" in the same instruction.

Implemented native message/tool loop, InMemorySaver, summary compaction, SSE transport
and incremental UI. Admin Documents/Products workflows remain. Removed old intent
models/parser, application MCP server, web adapter, filter/ranking APIs and unused card
components. Superseded proposal documents were consolidated into current requirements,
architecture, document management and verification; no credentials retained.

## Earlier decisions retained

- Assignment code must remain readable and organized; latest UI has exactly
  Assistant, Documents, Products. Recommendations/comparisons happen in chat.
- Company knowledge uses Weaviate hybrid retrieval and Google 1536-dimensional
  embeddings. Existing document IDs/content/revisions were preserved in migration.
- Neo4j stores20 fictional software products/39 plans with current-revision graph
  facts, typed specifications, prices, upgrade and complement relationships.
- Admin document replacement preserves identity and atomically publishes after
  indexing; concurrency conflicts and failed indexing preserve the prior version.
- Google service-account/ADC, Gemini 3.8 Flash, medium reasoning were live-verified.
- The previous linear workflow, web fallback and deterministic ranking were
  superseded. Their passing tests do not certify the new orchestration.
- A hidden persistent development launcher/logs were added after frontend stopped.

Current evidence and limitations: [verification](verification.md).

Final checks:129 backend tests,22 frontend tests,build and lint/format passed.
Live two-tool streaming and forced real-model compaction passed; detailed evidence
and current browser limitation are in verification.md.

## Markdown rendering and Langfuse

- User identified raw Markdown in chat; plain-paragraph rendering is being replaced
  with a safe Markdown/GFM renderer that updates during streaming.
- Installed the official Langfuse skill and read its instrumentation/CLI references,
  latest LangChain integration, best-practices, masking and usage docs.
- Tracing uses framework callbacks rather than duplicate manual model generations;
  each turn is one trace, with session IDs joining conversation turns. No hidden
  reasoning, credentials or private key values belong in trace exports/docs.
- Verification requires fetching exported observations, not just testing SDK calls.

- Final verification:143 backend tests and25 frontend tests pass, along with build,
  lint and formatting. Independent review exposed metadata-only raw exception/status
  leakage; fixed/tested, then fetched a live export proving the canary was absent
  from input,output and status while ERROR severity stayed visible.
- Fresh full exports have correct root/session grouping,all observations ended,
  native Gemini usage/cost data and no configured secret values. Verified example
  trace is linked from verification.md. The official skill remains installed.

## Trace-table correlation audit

User questioned whether mixed observation rows were orphan traces. Read current
Langfuse integration/best-practices docs and fetched modern observations directly.
The project contains39 observations grouped into5 test traces: two earlier test
turns12/7, two final corrected turns12/7, and one separate privacy-verification span.
Final trace e90ffcd384884e5894985539765aa67d contains12 observations; follow-up
3c2f970a3d8e47bc829712620dd188e3 contains7. Each has one isRootObservation=true
request and all child IDs resolve within that trace; both share one session.
The screenshot lists individual observation types, not proof of orphan traces.
No runtime change was made because correlation was verified. Opening a trace's
hierarchy, filtering to root observations, or grouping by trace ID clarifies the view.
The content-disabled top row is a deliberately separate privacy test, not a detached
production model/tool observation. Existing old test records were not deleted.

## Native MCP tool discovery and merging

The user supplied a unified MCP/native-tool agent example. Replaced the custom
neo4j_query wrapper and low-level MCP client with MultiServerMCPClient.get_tools().
Native get-schema/read-cypher objects are merged with company_rag and passed to
one agent; native schemas/executors stay intact. Tool discovery happens in async
application startup before the graph is compiled. Gemini,streaming,compaction,
Langfuse and the no-web constraint remain.

The example uses an older client context-manager API. Pinned adapter0.3.2 uses
get_tools() directly and manages per-call sessions. The standalone repository now
recommends a beta MCPAdapter in langchain[mcp]; this assignment uses the explicitly
requested MultiServerMCPClient pattern without adding that beta migration.
Reference: https://github.com/langchain-ai/langchain-mcp-adapters

## Neo4j explanation requested

User asked to understand the schema and full operation. Verified the live schema
via native MCP and counted20 active products/39 current plans. Added neo4j-guide.md
covering nodes,relationships,plan-specific features/prices,typed specifications,
revision publication,provenance/audit,IDs/constraints,native-agent querying and
current limitations. No application/database behavior was changed.

## In-place product Edit action

User requested product editing directly where the product is displayed. The UI
will expose an explicit Edit action,replace the selected detail with its prefilled
editor,and provide Save changes/Cancel. Preserve existing admin authentication,
product IDs,plan fields and revision-conflict behavior. No database/schema change
or cloud test mutation is required.

- Inline editing implemented: Edit on cards/details,Save changes/Cancel,blank Add
  flow,protected revision-aware publication and immediate updated details. During
  save,editing/navigation actions are disabled; conflicts preserve the draft.
  Frontend29 tests/build/format passed. No cloud product data was changed.

## Assistant banner removal and recommendation examples

Removed the screenshot's intro banner and model-information panel. Deleted their
unused component/styles/component tests; runtime model configuration remains intact.
User also requested example recommendation queries and an explanation of requirement-
led selection: task fit,hard constraints,preferences,graph evidence and tradeoffs.

## User-level REA MCP registration

User requested morluto/rea in Codex config.toml. Installed pinned rea-agents6.8.0
outside the project with an isolated,official-checksum-verified Node24.22.1 runtime,
because the existing Node24.18.0 does not meet this REA release's engine range.
Added a backed-up user-level mcp_servers.rea entry with absolute runtime/entrypoint
paths and compact input schemas,preserving all14 prior MCP registrations. MCP
initialization/tool discovery succeeded with229 tools. Codex must reload to load
this registration; Company Compass's runtime tool list/dependencies are unchanged.
No native analysis engines or matching workflow skills were installed by this
MCP-only registration.
