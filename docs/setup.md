# Setup details and troubleshooting

The project remains an assignment. Read the [production guardrail plan](production-readiness-plan.md)
before deploying it beyond local evaluation; controls described there as planned
are not enabled by copying environment variables.

`.env.example` lists every Settings field, with blank secrets, tracing content off
and admin writes disabled until a token is configured. Generate a token locally
and place it only in `.env` or managed secrets, for example:

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The root template is the only environment file intended for Git. Other environment
files, credentials/private keys and runtime logs are ignored. Ignore rules do not
untrack committed files or revoke credentials; audit history separately.

Follow the [README](../README.md) for ordered installation and first-run commands.
This page explains configuration, persistent state and recovery. It does not
introduce another deployment platform.

## Credentials and configuration

Copy `.env.example` once; do not overwrite an existing configured `.env` when
upgrading. Settings read that file from the repository root, with environment
variables taking precedence. Restart the backend after changes. Provider secrets
must not be put in frontend/Vite configuration.

| Component        | Authentication and permissions                                                                       |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| Gemini chat      | Vertex project/model/location and service account or ADC; identity must invoke the model             |
| Embeddings       | Google project, embedding model/location and Google credentials, even with API-key chat              |
| Neo4j repository | Connection/database credentials with catalog publication and explicit schema/index setup permissions |
| Neo4j MCP        | Absolute executable path; backend supplies Neo4j credentials and restricts it to schema/read tools   |
| Weaviate         | Cloud URL/API key with collection/vector setup and document-write access                             |
| Admin API        | Shared ADMIN_TOKEN; frontend retains the entered token only in component memory                      |
| Langfuse         | Optional project public/secret keys and base URL; unavailable tracing does not disable chat          |

Keep service-account JSON outside the checkout or in an ignored credentials folder.
For ADC, leave `GOOGLE_APPLICATION_CREDENTIALS` blank and run
`gcloud auth application-default login`. Selected models and locations must be
available to your project; a green configuration/health response does not verify access.

## Data initialization and persistence

The locked neo4j-mcp-server package installs `.venv/Scripts/neo4j-mcp-server.exe`
on Windows and `.venv/bin/neo4j-mcp-server` on macOS/Linux. Its help banner may
call the underlying binary neo4j-mcp; configure the actual installed executable.

Cloud order: `check`, `seed`, `index-catalog`, `ingest`, `mcp-check`.

- Seed adds missing products and initializes constraints; existing edits survive.
- Index-catalog creates indexes, checks dimensions, waits for readiness and embeds
  current products without creating new publication revisions.
- Ingest publishes document chunks and a manifest; inspect its warnings.
- MCP-check tests native tools without invoking the chat model.

The Weaviate implementation creates HFresh indexes. Use a compatible Cloud cluster;
another index type requires an explicit implementation/configuration change.
Neo4j retrieval uses compatible vector/full-text procedures rather than requiring
the newest Cypher SEARCH syntax.

The default `data/runtime/knowledge.json` manifest identifies active document
versions. Its cloud namespace includes the endpoint and collection. Preserve and
back up this file: cloud vectors alone cannot reconstruct publication ownership.
Local catalog snapshots default to `data/runtime/catalog.json`; cloud products
and revision history are authoritative in Neo4j.

## Existing data and embedding changes

Do not mix vectors from different models or dimensions silently. For a legacy
Weaviate auto-vectorized collection, retain its manifest, select cloud mode,
`EMBEDDING_PROVIDER=vertex`, the desired named vector and 1536 dimensions, then run:

```powershell
uv run company-compass migrate-embeddings
```

The command embeds and verifies active document chunks without changing content,
IDs or publication revisions. Legacy vectors remain. This migration is limited
to 500 published chunks and 1536 dimensions. Inspect its result before restarting
chat with the new settings. New empty collections use normal ingestion instead.

For the catalog, rerun `index-catalog` after changing embedding models. A dimension
mismatch requires explicit index migration. Index names are application-owned;
setup does not repair externally created same-name indexes with other properties
or metrics. See [catalog hybrid search](catalog-hybrid-search.md).

## Troubleshooting

| Symptom                        | Check                                                                                           |
| ------------------------------ | ----------------------------------------------------------------------------------------------- |
| MCP discovery fails            | Absolute executable path, installed neo4j-mcp extra, Aura availability and actual database name |
| Health is green but chat fails | Google credentials, project/model permissions and configured locations                          |
| Catalog search unavailable     | Run cloud index-catalog; check vector model/dimensions and embedding permissions                |
| No company evidence            | Ingest warnings, Documents list and the expected manifest/Weaviate namespace                    |
| Weaviate indexing fails        | API-key permissions, cluster HFresh support and named-vector configuration                      |
| Product save fails             | Admin token and embedding access; embeddings must succeed before publication                    |
| Edit returns 409               | Reload the latest record and reconcile the preserved draft                                      |
| Old settings remain            | The launcher skips healthy services; restart the backend                                        |
| UI cannot reach API            | Backend on 8010 and Vite on 5173; /api is proxied to 8010                                       |
| Missing Langfuse trace         | Keys/base URL/enabled flag and export logs; chat runs independently of tracing                  |

Windows launcher logs: `data/runtime/backend.stdout.log`, `backend.stderr.log`,
`frontend.stdout.log`, `frontend.stderr.log`. Keep runtime logs out of version
control. CLI failures expose a safe error type instead of credential-bearing
provider exception text. A failed document index preserves its previous publication.

## Running and hosting

The Windows launcher binds loopback and starts missing services in hidden windows;
it does not forcibly restart healthy processes. Foreground commands in the README
can be stopped with Ctrl+C. Backend restart clears conversation memory.

Production hosting must route `/api` to FastAPI, serve the frontend build, fall
back to `index.html` for `/admin`, and preserve document manifests. Production
process supervision, user login and deployment-specific secrets management are
outside the assignment's implemented scope.
