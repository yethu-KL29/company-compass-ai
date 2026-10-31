import { useEffect, useState, type FormEvent } from "react";
import { FilePenLine, RefreshCw } from "lucide-react";
import { api, ApiError, errorMessage } from "../../services/api";
import { useDocuments } from "./useDocuments";
import type { CompanyDocument } from "../../models/types";
import { DocumentMetadata } from "./DocumentMetadata";

export function DocumentManager({
  token,
  refreshKey,
}: {
  token: string;
  refreshKey: number;
}) {
  const {
    documents,
    loading,
    error: listError,
    reload,
  } = useDocuments(refreshKey);
  const [selected, setSelected] = useState("");
  const [document, setDocument] = useState<CompanyDocument | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [conflict, setConflict] = useState(false);
  const [detailRefresh, setDetailRefresh] = useState(0);

  useEffect(() => {
    if (!selected) {
      setDocument(null);
      return;
    }
    let cancelled = false;
    setReading(true);
    setDocument(null);
    setError("");
    setSuccess("");
    setConflict(false);
    api
      .document(selected)
      .then((value) => {
        if (!cancelled) {
          setDocument(value);
          setTitle(value.title);
          setContent(value.content);
        }
      })
      .catch((failure) => {
        if (!cancelled) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!cancelled) setReading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected, detailRefresh]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!document) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const saved = await api.updateDocument(
        document.id,
        title,
        content,
        document.revision,
        token,
      );
      setDocument(saved);
      setTitle(saved.title);
      setContent(saved.content);
      setConflict(false);
      setSuccess(
        `Published document revision ${saved.revision}. The replacement is now available to retrieval.`,
      );
      reload();
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409) {
        setConflict(true);
        setError(
          `${errorMessage(failure)}. Your edits are preserved. Reload the published version before editing again; reloading discards these unsaved changes.`,
        );
      } else if (failure instanceof ApiError && failure.status === 502) {
        setError(
          `${errorMessage(failure)}. Your edits are preserved and the previous published document remains available. You can retry.`,
        );
      } else setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section
      className="panel editor document-manager"
      aria-label="Admin document management"
    >
      <div className="editor-heading">
        <div>
          <h2>Review and update documents</h2>
          <p className="small muted">
            Edit the full text, then replace its active indexed version.
          </p>
        </div>
        <FilePenLine size={22} />
      </div>
      {listError && (
        <p className="notice error" role="alert">
          {listError}
        </p>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {success && (
        <p className="notice success" role="status">
          {success}
        </p>
      )}
      <label>
        <span>Document to edit</span>
        <select
          value={selected}
          disabled={loading || saving || reading}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="">
            {loading ? "Loading documents…" : "Choose a published document"}
          </option>
          {documents.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title} · revision {item.revision}
            </option>
          ))}
        </select>
      </label>
      {!loading && !listError && !documents.length && (
        <p className="notice small">
          No documents yet. Upload a document or add an official source URL
          above.
        </p>
      )}
      {reading && (
        <p className="notice" role="status">
          Loading the full document…
        </p>
      )}
      {document && (
        <form onSubmit={save}>
          <DocumentMetadata document={document} />
          <label>
            <span>Document title</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              disabled={saving}
              readOnly={conflict}
            />
          </label>
          <label>
            <span>Full document content</span>
            <textarea
              className="document-editor-content"
              rows={15}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              required
              disabled={saving}
              readOnly={conflict}
            />
          </label>
          <p className="small muted">
            Saving re-ingests the edited content. The current published document
            remains available until its replacement is indexed successfully.
          </p>
          {saving && (
            <p className="notice" role="status">
              Indexing the replacement. The previous published version remains
              available…
            </p>
          )}
          <div className="document-actions">
            {conflict ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => setDetailRefresh((value) => value + 1)}
              >
                <RefreshCw size={15} />
                Reload published version (discards edits)
              </button>
            ) : (
              <button
                className="button primary"
                disabled={
                  !token.trim() || saving || !title.trim() || !content.trim()
                }
              >
                {saving ? "Saving and re-ingesting…" : "Save and re-ingest"}
              </button>
            )}
          </div>
        </form>
      )}
    </section>
  );
}
