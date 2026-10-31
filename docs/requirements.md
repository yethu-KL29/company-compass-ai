# Confirmed assignment requirements

## Production plan and repository hygiene

User requested a production guardrail plan in the README/documentation, proper
environment-file ignore rules, a complete secret-free .env.example, professional
repository conventions and a GitHub push. Production control recommendations must
be distinguished from implemented assignment behavior. Keep the working architecture
and avoid presenting unimplemented guardrail infrastructure as complete.

## Recommendation presentation

User requested that recommendations stop repeating a demo disclaimer. The assistant
should lead with relevant plans, constraints and evidence. Existing UI/documentation
labels retain the catalog's synthetic status; questions about authenticity must be
answered honestly. Products must not be presented as verified official offerings.

## Catalog semantic discovery (confirmed)

Embed product descriptions and use cases, create Neo4j vector/full-text indexes,
retrieve the top five product nodes and supply their fixed relationship context
to the agent. Keep the single-agent workflow and native MCP access. Admin product
edits must update searchable content; search relevance is separate from mandatory
price/capacity eligibility. This supersedes Text-to-Cypher-only catalog discovery.

## Public experience (confirmed 2026-10-31)

Use Attoforce's theme concept for a separate user-facing page with a floating chat
widget. User explicitly prioritizes architecture over copying the website exactly.
Reuse the existing agent call and chat components; preserve the current workspace
for document/product administration. The chosen entry paths are `/` and `/admin`.
No agent, retrieval, MCP, memory or API changes are part of this presentation update.

User subsequently requested the same black theme for the admin workspace. Apply
the dark palette to its navigation, panels, forms and status states; retain the
existing administration behavior.

Latest user direction,2026-10-31, supersedes earlier architecture proposals.

- Python application with readable models, agents, services, integrations, utilities and
  a small application entrypoint; document actual architecture and setup.
- One LangGraph agent receives each user query directly. Two tool integrations: company
  document RAG and the Neo4j MCP server for catalog querying. The model chooses tools
  through its system prompt and can investigate results over multiple calls.
- Remove web search and the fixed plan/retrieve/answer intent pipeline. Product
  recommendations and comparisons come from catalog facts and relationships.
- Keep a separate workflow file, stream answers and use in-memory LangGraph memory
  with conversation compaction.
- Gemini 3.8 Flash with medium reasoning and supplied Google service-account
  authentication; company embeddings1536 dimensions.
- Weaviate hybrid retrieval for company documents; Neo4j for fictional demo products,
  plans, capabilities, prices, specifications, upgrade/complement relationships.
- Exactly three UI sections: Assistant, Documents, Products. Recommendations and
  comparisons are conversational. No standalone filter/comparison/Admin menu.
- Admins can upload, read, edit and replace documents through re-ingestion under stable
  IDs/titles. Product details/plans can be added/updated with revision checks.
- Keep only relevant documentation and remove superseded source files.

## Implementation defaults and limits

The tool loop is iteration-bounded. Each browser chat uses an opaque thread ID;
state remains in one backend process and resets on restart. Compaction summarizes
older completed turns and preserves recent complete tool-call/result groups.

The catalog is explicitly synthetic, not real Attoforce pricing. The current seed
has20 products/39 plans. No behavioral personalization, DRIFT/GDS, scheduled refresh,
OCR, production deployment or persistent chat storage is required.

## Markdown and observability update

User requested Markdown rendering in streamed chat and Langfuse observability,
using the official Langfuse skill installed from github.com/langfuse/skills.
Trace one request per turn, group turns by conversation, and expose model/tool/
compaction execution, usage, latency and failures. Credentials remain in ignored
configuration. Trace content is optional and must be masked before export;
local public/synthetic demo tracing enables sanitized input/output for debugging.
The runtime retains the same RAG/Neo4j integrations and single-agent workflow.

## Native MCP tool merging

User clarified the concrete pattern: discover MCP tools through
MultiServerMCPClient.get_tools(), merge them with the local RAG tool and bind the
unified list to one agent. Preserve native MCP names,schemas and executors.
Neo4j currently exposes get-schema and read-cypher; with company_rag this means
three callable functions from two integrations. No custom neo4j_query wrapper,
params_json shim,web search,OpenAI switch or sample calculation tool is requested.
Async startup discovers tools before compiling the one LangGraph workflow.

## In-place product editing

User requested an Edit button on the product itself. Selecting Edit opens the
existing product and plans in place on the Products screen,with Save changes and
Cancel. Existing product identity and optimistic revision checks remain; publishing
continues to require the admin token. Add product opens a blank editor. A separate
always-visible editor below the read-only details is unnecessary.

## Assistant screen cleanup

User requested removal of the introductory eyebrow/title/description and selected
model/reasoning/authentication panel shown above chat. Assistant now opens directly
with the chat interface; backend model configuration and health checks are unchanged.
