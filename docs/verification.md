# Verification

2026-10-31. Evidence applies to the final two-tool LangGraph refactor.

| Check | Result |
| --- | --- |
| Backend pytest | 137 passed after native MCP refactor; includes tracing, tool selection, streaming, memory, cancellation and admin/ingestion regressions |
| Frontend | 25 tests passed, TypeScript/Vite production build and Prettier passed |
| Python | Ruff lint/format and whitespace checks passed |
| Tool boundary | Exactly company_rag and neo4j_query; no web tool, fixed planner or application MCP wrapper |
| Native tool loop | Model-selected successive tool calls, no-tool greeting, native messages/signatures and iteration bound covered |
| Streaming | Actual HTTP SSE delivered multiple token events before completion; frontend tests verify partial UTF-8/frames and text before done |
| Admin regression | Document upload/edit/re-ingestion, ID/revision preservation, indexing failure, conflicts and product publishing pass isolated tests |

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
