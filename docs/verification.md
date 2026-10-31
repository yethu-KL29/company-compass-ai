# Verification

## Environment hygiene and production planning

Expanded ignore patterns cover local environment files, credential/private-key
files and runtime logs while retaining only the root .env.example. All 36 Settings
fields are represented exactly once in the template, with blank credentials;
parsing confirms admin publication is disabled without a configured token and
trace content capture is off. Ignore behavior was checked with representative
root/nested environment and secret paths.

A read-only security specialist reviewed current controls and production gaps.
Identity/thread ownership, independent query scope, aggregate budgets, output
validation before streaming and retention/persistence remain planned release gates.
No penetration test or dependency vulnerability scan is claimed. Added editor and
line-ending conventions without mass source refactoring. All 13 Mermaid charts
passed parser validation; local documentation links were checked separately.

All 161 backend tests passed after this change. Configured-secret values were
checked against tracked history and the working diff, with no matches; no actual
credentials were printed or placed in the template. The runtime .env was unchanged.

## Recommendation wording update

Removed the instruction to repeat a fictional/demo preamble on every recommendation.
UI disclosures and truthful authenticity handling remain. All 161 backend tests
passed. After backend restart, the user's 8,000-invoice / human-review / API /
INR20,000 requirement completed with 44 token events and no errors. The answer
led with requirements and plan recommendations. Trace ID:
`37b9c7b301494db39b1b6bc3ca13837f`. This is one observed response, not a guarantee
of identical wording on every model generation. Outgoing commits were checked
against configured secret values before the user-authorized GitHub push.

## Documentation and setup review

README now includes installation, cloud configuration, Google auth, native MCP
executable resolution, seed/index/ingest order, user/admin URLs, inline Mermaid
diagrams, four-tool behavior and local-mode limits. Added setup/migration and
troubleshooting guidance. Configuration was checked against Settings, CLI, package
metadata, launcher and storage implementations.

`uv sync --frozen --extra dev --extra neo4j-mcp --python 3.12 --dry-run` reported
no environment changes. CLI help and the installed MCP executable's help succeeded.
The locked package installs neo4j-mcp-server.exe, correcting the earlier path.
Local links across 12 Markdown files resolved. These are documentation checks,
not a fresh-machine installation or a repeat of cloud initialization. No runtime
behavior, credentials or cloud records changed in this update.

All 12 Mermaid blocks across README and top-level docs passed Mermaid 11.17.2
parser validation. Modified Markdown formatting and git whitespace checks passed.

## Catalog hybrid search

- 161 backend tests passed; Ruff lint and formatting passed. Focused tests cover
  text selection, vectors, lexical escaping, fusion query arguments, native MCP
  response parsing, graph context, safe failures, publication failure isolation,
  revision checks and retirement. Native tools retain their identity.
- Live `index-catalog` created the vector/full-text indexes and embedded 20
  products with gemini-embedding-001 at 1536 dimensions; no concurrent updates
  were skipped. Product revisions and document data were not replaced.
- Native MCP search for document automation/invoice extraction returned five
  current products with relationship context; DocPilot ranked first by discovery
  score. This verifies connectivity, query execution and native result parsing,
  not a measured recall benchmark.
- Restarted the backend to load the new tool. A real streamed chat called
  catalog_search then read-cypher, emitted 41 token events and completed without
  errors. Trace ID: `0b92235941e542f594a29ea782900323`.
- The frontend was unchanged by this retrieval feature. Single-host memory reset
  on restart as documented. Independent integration review found no blocking
  regression; externally pre-existing incompatible index names remain a documented
  setup limitation.

## Assistant identity and Mermaid diagrams

Shared chat heading and answer labels now use Attoforce assistant. All 32 frontend
tests, production build and formatting checks passed. Seven charts in
`architecture-diagrams.md` passed Mermaid 11.17.2 parser validation; a sequence
message separator caught by that check was corrected. These are syntax-validated
charts, not a claim of visual layout auditing. Validation dependencies stayed in
ignored `data/runtime/`; application dependencies and agent behavior are unchanged.

## Public page and shared chat widget (2026-10-31)

- All 32 frontend tests passed, including public/admin entry selection, opening
  without an agent request, Escape/focus restoration, Markdown rendering and
  conversation/server-thread retention after minimizing.
- Production build, Prettier checks and `git diff --check` passed. Backend source
  and tests are unchanged; the earlier backend verification remains the baseline.
- REA captured the official site's theme and the local public page at 1440px.
  Desktop widget and 375x812 mobile captures show the composer and Close/New chat
  controls within the viewport. Visual inspection found and corrected inherited
  navigation/flex alignment and diagram-label positioning.
- Desktop REA captures completed but reported cleanup timeouts; evidence was
  recovered from partial observations. The mobile run completed with owned browser
  termination confirmed. This is not a full accessibility audit or device test.
- Root and `/admin` returned HTTP 200 from Vite. Streaming transport remains the
  existing tested implementation; no new live model request or catalog mutation
  was performed for this frontend change. Production SPA fallback is documented.
- Subsequent admin black-theme update: production build passed; REA captured the
  Products navigation, admin-token form, search and loading state in dark colours.
  That scenario completed with owned browser termination confirmed. No admin save
  or cloud mutation was executed. Palette-only changes add no new behavior tests.

2026-10-31. Evidence applies to the final two-tool LangGraph refactor.

| Check            | Result                                                                                                                                  |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Backend pytest   | 137 passed after native MCP refactor; includes tracing, tool selection, streaming, memory, cancellation and admin/ingestion regressions |
| Frontend         | 25 tests passed, TypeScript/Vite production build and Prettier passed                                                                   |
| Python           | Ruff lint/format and whitespace checks passed                                                                                           |
| Tool boundary    | Exactly company_rag and neo4j_query; no web tool, fixed planner or application MCP wrapper                                              |
| Native tool loop | Model-selected successive tool calls, no-tool greeting, native messages/signatures and iteration bound covered                          |
| Streaming        | Actual HTTP SSE delivered multiple token events before completion; frontend tests verify partial UTF-8/frames and text before done      |
| Admin regression | Document upload/edit/re-ingestion, ID/revision preservation, indexing failure, conflicts and product publishing pass isolated tests     |

## Live evidence

- Actual recommendation via SSE used three Neo4j MCP queries, inspected plans and
  relationships, and compared LeadPilot Growth with WorkSuite Team against 10 users,
  API and INR 10000/month per organization. The two plans were INR 7500 and INR 9000;
  automation-rule capacity differed 5 versus 20. The model selected its own calls.
- The same thread answered which of those products was cheaper and explained losses
  without requiring the browser to resend history.
- Company-document query selected company_rag and returned Weaviate evidence with
  stable document IDs/provenance.
- A forced 500-token compaction test with the real model summarized an earlier RAG
  turn into 1511 characters, retained 2 messages, and correctly recalled 10 users,
  INR 10000/month per organization and mandatory API. The production threshold remains
  6000; the lower value was test-only.
- A product run delivered first public text at 44.56 seconds and completed at 50.20s;
  follow-up began at 4.03s and completed at 8.06s. These are single smoke observations,
  not latency guarantees. MCP process startup contributes overhead.

## Bugs reproduced and corrected

- Native tool-call history sent to an unbound summarizer caused a live Gemini
  invalid-request error. Summarization now takes a plain serialized transcript as
  untrusted data, rather than replaying native function-call messages.
- Empty summaries previously discarded history. Nonempty summary validation now
  fails safely before RemoveMessage; prior completed state is restored.
- AnyIO cancellation could interrupt checkpoint replacement after deletion.
  Shielded cleanup now preserves prior completed turns; regression reproduces this
  specific cancellation scope.
- Closing the SSE body did not promptly close the nested assistant generator.
  Explicit async-generator ownership now cancels/rolls back immediately.
- Live script exit exposed an unclosed async model client. Application shutdown now
  awaits its close method before releasing storage resources.

## Limits

No current visual browser check is claimed: the in-app browser is unavailable and
browser inventory is empty. Component tests and real HTTP streaming are separate
verification evidence. Cloud document/product mutations were not repeated; tests
use isolated storage. No public deployment, load/quality benchmark, exhaustive
recommendation evaluation or production security certification is claimed.

InMemorySaver is process-local. Older completed checkpoints are discarded, but idle
threads remain in memory until restart; no long-lived session eviction system is
included. Compaction is approximate and lossy. Successful smoke cases do not prove
all generated Cypher or answer claims are correct.

## Reproduce

```powershell
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
cd frontend
npm test
npm run build
npm run format:check
```

Use the launcher and POST `/api/chat/stream` with a new message; reuse returned
thread_id for follow-ups. Changing memory settings requires backend restart.

## Markdown and Langfuse verification

Official Langfuse skill installed from langfuse/skills; current instrumentation,
CLI, integration, best-practices, masking and token-tracking guidance was read.
Langfuse SDK 5.1.0 is locked. Markdown uses react-markdown 10.1.0/remark-gfm 4.0.1.

- Frontend 25 tests, production build and formatting passed, including streamed/
  completed headings, lists, emphasis, tables, links and code. Raw HTML, unsafe URLs
  and remote image loads are disabled. User messages remain literal.
- Native SDK export tests cover hierarchy/session correlation, exclusive cached/
  reasoning usage, missing usage, cancellation, disabled tracing and masking.
  No duplicate model wrapper is installed.
- Actual export was fetched with langfuse-cli observations list (modern API), not
  inferred from SDK calls. First run exposed missing root session context; fixed
  attribute propagation was verified with fresh live exports.
- Trace e90ffcd384884e5894985539765aa67d has 12 observations, one request root,
  RAG/Neo4j tools and two Gemini generations. Follow-up trace
  3c2f970a3d8e47bc829712620dd188e3 has 7 observations including compaction and answer
  generations. Both have correct session IDs on every observation; all ended.
- Four generation usage bucket sums match provider totals. Model names, latency and
  Langfuse price-based cost estimates are present, not independent billing records.
  No configured secret values appeared in fetched observations. The SDK public
  project-key routing identifier may appear in scope metadata; it is not a secret.
- Content defaults off; the user's local public/synthetic demo enables masked
  input/output capture. Redaction is defensive, not exhaustive PII classification.

Verified [tool trace](https://cloud.langfuse.com/project/cmvw6f7qx03egad0k9e19tlr7/traces/e90ffcd384884e5894985539765aa67d).
No new visual browser verification is claimed; automated rendering and live trace
export checks are distinct evidence. Final regression:143 backend tests,25 frontend tests,production build and lint/format passed.
Independent review caught metadata-only raw error/status content; regression and
live export verification now prove input/output/error-message canary text is hidden
with capture off while ERROR severity remains. No inference was used for this probe.

Correlation re-audit after the user's table screenshot: modern API returned39
observations across5 known test requests, not39 independent traces. Final12/7
observation turns each have one root, internally resolved child-parent links and
one shared conversation session. Separate privacy probe contains only its root.
No additional tracing decorator or runtime changes were needed.

## Native MCP merge verification

- Replaced custom MCPquery wrapper/low-level client with pinned
  langchain-mcp-adapters0.3.2 MultiServerMCPClient.get_tools().
- Native schema/read tool objects and argument schemas are preserved in
  [*mcp_tools,company_rag] and bound to the same agent. Async startup initializes
  exactly once; no catalog tool is invoked merely to classify a user query.
- 137 backend tests pass. Removed obsolete custom query-parser/wrapper tests;
  replacements cover native schema/object identity,read-only server configuration,
  rejected unexpected write tools,real local stdio discovery/invocation and startup.
- Live Aura discovery returned get-schema/read-cypher with their native schemas.
  Gemini accepted those tools, called get-schema/company_rag/read-cypher and streamed
  a catalog recommendation. Native params objects reached the server unchanged.
- Google tool-schema conversion logs that additionalProperties is ignored; native
  discovery/invocation worked in the representative live run without application
  schema rewriting. The custom params_json shim is removed.
- Verified example trace:
  https://cloud.langfuse.com/project/cmvw6f7qx03egad0k9e19tlr7/traces/dd077e1827104f3b97d70ef9cb3223d6
- Frontend unchanged by this refactor; previous25-test Markdown/SSE suite remains
  applicable. No new visual browser verification is claimed.

## In-place product editing

Frontend29 tests,production build and formatting passed. Regressions cover card/
detail Edit actions,prefilled fields,immutable IDs,Save authentication and original
revision,immediate updated details,Cancel without a request,blank creation,disabled
save without a token,and preservation of drafts on conflict. No cloud product was
changed for verification. Backend unchanged; earlier backend suite remains the
applicable baseline. Current dev-server health and changed TSX modules returned200.

## Assistant banner removal

Removed the intro heading/description and model-information panel requested in the
screenshot,along with their unused component/styles and two component tests.
Remaining27 frontend tests and production build passed. Backend/model configuration
unchanged. Recommendation prompts were documented against the existing demo data.
