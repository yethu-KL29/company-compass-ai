# Company Compass interface

React, TypeScript and Vite with three sections:

- **Assistant:** streamed company answers, recommendations and comparisons in chat.
- **Documents:** read, upload, edit and re-ingest company documents.
- **Products:** view and maintain synthetic products, plans and specifications.

## Run and verify

Start the backend on port 8010, then run from this directory:

```powershell
npm ci
npm run dev
npm test
npm run build
npm run format:check
```

Vite serves port 5173 and proxies `/api` to the backend. Production hosting needs
its own API routing.

## Structure

```text
src/
  App.tsx                 Three-section navigation and shared admin token
  features/assistant/     Chat view, streaming state hook, sources
  features/documents/     Library, upload and revision-aware editor
  features/products/      Product details and product/plan/specification forms
  components/ui/          Shared token and list controls
  services/api.ts         API requests, authentication and typed errors
  services/chatStream.ts  Incremental UTF-8/SSE decoding
  models/types.ts         API contracts
  utils/format.ts         Price formatting
  test/                   Component and streaming transport checks
```

## Chat contract

`POST /api/chat/stream` sends `{message, thread_id?}` and accepts SSE JSON events:
`session`, `token`, `tool`, `done` and `error`. The UI displays text as tokens arrive;
RAG citations and warnings appear on completion. Recommendations and comparisons
are part of the model's answer, without separate filters or comparison screens.

The server owns conversation memory and compaction. The client retains the server's
thread ID in component memory and does not replay browser history. **New chat**
aborts an active stream, clears the conversation and starts a fresh thread. Unmount
also aborts the request. Network/server failures retain partial text and display an
error; partial output is never treated as a completed answer.

## Admin workflows

Documents and Products share an admin token held only in App memory. Public records
are readable; every write is authorized by the backend. No model/database credentials
belong in frontend environment variables.

Uploads are multipart `POST /api/admin/documents/upload` with file/title. Supported
formats are TXT, Markdown, PDF and DOCX; the title limit is 250 characters and file
limit 10,000,000 bytes. Uploaded documents have a null source URL and admin provenance.
Edits send the original revision; conflicts retain unsaved changes. Product updates
also send their expected revision. Text is never rendered as executable HTML.

Tests cover incremental text before completion, UTF-8/frame boundaries, thread reuse,
new-chat/unmount cancellation, interrupted streams, server errors, navigation and
admin operations. Mocked tests do not establish live provider integration. Current
streaming UI visual checks are reported separately by the parent verification run.
