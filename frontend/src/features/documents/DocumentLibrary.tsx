import { useEffect, useState } from "react";
import { FileText, RefreshCw } from "lucide-react";
import { api, errorMessage } from "../../services/api";
import { useDocuments } from "./useDocuments";
import type { CompanyDocument } from "../../models/types";
import { DocumentMetadata } from "./DocumentMetadata";

export function Documents({
  refreshKey = 0,
  showHeading = true,
}: {
  refreshKey?: number;
  showHeading?: boolean;
}) {
  const { documents, loading, error, reload } = useDocuments(refreshKey);
  const [selected, setSelected] = useState("");
  const [document, setDocument] = useState<CompanyDocument | null>(null);
  const [detailError, setDetailError] = useState("");
  const [reading, setReading] = useState(false);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setReading(true);
    setDetailError("");
    setDocument(null);
    api
      .document(selected)
      .then((value) => {
        if (!cancelled) setDocument(value);
      })
      .catch((failure) => {
        if (!cancelled) setDetailError(errorMessage(failure));
      })
      .finally(() => {
        if (!cancelled) setReading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  function refresh() {
    setSelected("");
    setDocument(null);
    reload();
  }
  return (
    <section>
      {showHeading && (
        <div className="section-intro">
          <div>
            <div className="eyebrow">The knowledge behind the answers</div>
            <h1>Read the source material.</h1>
            <p className="muted">
              Browse published company documents and the full content currently
              available to the assistant.
            </p>
          </div>
          <button
            className="button secondary"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw size={15} />
            Refresh documents
          </button>
        </div>
      )}
      {!showHeading && (
        <div className="editor-heading document-library-heading">
          <h2>Published documents</h2>
          <button
            className="button secondary compact"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {loading && (
        <p className="notice" role="status">
          Loading company documents…
        </p>
      )}
      {!loading && !error && !documents.length && (
        <div className="empty-state panel">
          <FileText size={30} />
          <h2>No published documents yet</h2>
          <p className="muted">
            An administrator can upload approved company documents using the
            form above.
          </p>
        </div>
      )}
      {!!documents.length && (
        <div className="documents-layout">
          <aside
            className="panel document-list"
            aria-label="Published documents"
          >
            <div className="panel-heading">
              <h2>Documents</h2>
              <span className="badge outline">{documents.length}</span>
            </div>
            {documents.map((item) => (
              <button
                key={item.id}
                className={`document-list-item ${selected === item.id ? "active" : ""}`}
                onClick={() => setSelected(item.id)}
                aria-pressed={selected === item.id}
              >
                <strong>{item.title}</strong>
                <span className="small muted">
                  {item.id} · revision {item.revision}
                </span>
                <span className="small muted">
                  {item.source_kind === "admin_edit"
                    ? "Admin-edited"
                    : item.source_kind === "admin_upload"
                      ? "Uploaded document"
                      : item.source_kind.replaceAll("_", " ")}{" "}
                  · {item.chunk_count} chunks
                </span>
                <span className="small muted">{item.source_url}</span>
              </button>
            ))}
          </aside>
          <article
            className="panel document-reader"
            aria-label="Document content"
            aria-busy={reading}
          >
            {reading && <p role="status">Loading the full document…</p>}
            {detailError && (
              <p className="notice error" role="alert">
                {detailError}
              </p>
            )}
            {!selected && (
              <div className="empty-state">
                <FileText size={28} />
                <h2>Choose a document</h2>
                <p className="muted">
                  Read its published content, revision and source details.
                </p>
              </div>
            )}
            {document && (
              <>
                <h2>{document.title}</h2>
                <DocumentMetadata document={document} />
                <div className="document-content">{document.content}</div>
              </>
            )}
          </article>
        </div>
      )}
    </section>
  );
}
