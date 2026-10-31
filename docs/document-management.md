# Human-maintained documents and products

2026-10-31. User requested human support for both knowledge documents and catalog products. Product editing/publication already exists; this change adds document discovery, readable content and edit/re-ingestion.

## Document identity and user workflow

The Documents screen lists published documents with stable ID, readable title, source URL, revision, observation time and chunk count. Selecting one shows its associated full text. Ordinary users can inspect the published company knowledge; only an authenticated admin can change it.

An admin selects a document, edits its title/content, and chooses **Save and re-ingest**. The stable ID and source URL remain unchanged. This is a replacement publication, not a duplicate document. Browser edits are drafts until the admin triggers publication; a second-person approval is not required in this assignment.

Admins can also upload TXT, Markdown, text-based PDF or DOCX with a required title
(maximum 250 characters). Files are limited to 10,000,000 bytes, extracted text to
2 MB, PDFs to 100 pages and expanded DOCX content to 20 MB. Scanned/empty PDFs need
OCR and are rejected. Uploaded documents have `admin_upload` provenance, a stable
generated ID and a null source URL. Editing uses the same replacement pipeline.

## Pipeline

1. Authenticate the admin; validate title, nonempty content and expected revision.
2. Compare the submitted revision with the current publication; return 409 on conflict, preserving unsaved browser edits.
3. Build chunks and a content version from the full title/content. Identical edits are idempotent and do not re-embed.
4. Stage/index the new chunks. The previous publication stays available during this step.
5. After indexing succeeds, atomically publish the new document manifest with the same ID and an incremented revision. Current retrieval rejects obsolete versions, including when a read overlaps an update.
6. Clean up superseded cloud vectors after successful publication. A cleanup failure reports a warning but cannot undo a successful replacement; obsolete chunks remain excluded by the manifest.
7. On indexing failure, return 502 and retain the exact previous title, content and revision. Newly staged incomplete chunks are not searchable and can be reused on retry.

The pipeline is synchronous and bounded for the small assignment: the UI shows an in-progress state while the request runs. A canonical manifest file lock serializes the full read/index/publish/cleanup transaction across API and CLI processes on the same host; a 60-second lock timeout returns a conflict. This prevents stale CLI refresh from overwriting a concurrent admin edit. A real subprocess regression verifies the race. No queue or background-worker platform is introduced.

## Provenance and refresh ownership

Original URL ingestion marks a document `official_web`. An edited replacement is `admin_edit`; document views and answer sources identify that distinction so an admin's wording is not misrepresented as verified official page text. The original URL is retained as source context, not a guarantee that edited claims appear there.

URL refresh skips an admin-edited document with a warning. It cannot silently overwrite human edits. Explicit admin replacement controls the published content. A future reset-to-source feature would need its own clear action.

Legacy records created before this change remain visible. IDs are deterministically derived from dataset and source URL; titles and content are reconstructed from their ordered chunks, removing chunk overlap. Subsequent edits store the exact full content. Fresh content has a structured title/content hash rather than ambiguous string concatenation.

## API

| Endpoint | Access | Behavior |
| --- | --- | --- |
| GET /api/documents | Public | Metadata list; no full content duplication |
| GET /api/documents/{id} | Public | Published metadata and full content |
| POST /api/admin/documents/upload | Admin token | Multipart file/title -> extraction and indexed publication |
| PUT /api/admin/documents/{id} | Admin token | title, content, expected_revision -> replacement publication |
| POST /api/admin/ingest | Admin token | Initial official URL ingestion/refresh; skips human-owned edits |

Document metadata includes `id`, `title`, `source_url`, `revision`, `version`, `observed_at`, `source_kind`, and `chunk_count`. Full document responses add `content`; successful replacements may include cleanup warnings. The assistant's sources add `document_id`, `document_revision` and `source_kind`.

## Scope

Text editing and TXT/Markdown/PDF/DOCX uploads are implemented. A second-reviewer queue, OCR and persistent draft history are not included. The single-host manifest remains on persistent local disk. Active embeddings migrated to Google's `gemini-embedding-001`, 1,536 dimensions, with all ten original chunks verified. The original document IDs and publication revisions were preserved; old default vectors remain for rollback.

Tests cover legacy discovery, stable IDs, exact content/title updates, stale revisions, failed indexing, obsolete chunks, idempotency, refresh ownership and protected API publication.

## Product editing in place

Products now expose Edit on each card and Edit product in the selected detail.
The action replaces the detail with the prefilled product/plan editor and focuses
its name field. Existing product IDs remain immutable. Save changes sends the
admin token and original revision,then immediately displays the returned product
revision. Cancel discards changes without a request. Add product opens a blank form.
Saving locks the current editor and selection actions; conflict responses preserve
unsaved input. The standalone always-visible editor/dropdown has been removed.
