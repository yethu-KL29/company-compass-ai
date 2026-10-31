import { useState, type FormEvent } from "react";
import { Upload } from "lucide-react";
import { api, errorMessage } from "../../services/api";

const MAX_FILE_BYTES = 10_000_000;
const SUPPORTED_FILES = /\.(txt|md|pdf|docx)$/i;

export function DocumentUpload({
  token,
  onUploaded,
}: {
  token: string;
  onUploaded: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [pending, setPending] = useState(false);

  function selectFile(value: File | undefined) {
    setError("");
    setSuccess("");
    setFile(null);
    if (!value) return;
    if (!SUPPORTED_FILES.test(value.name)) {
      setError("Choose a .txt, .md, .pdf or .docx document.");
      return;
    }
    if (value.size > MAX_FILE_BYTES) {
      setError("Choose a document smaller than 10 MB.");
      return;
    }
    setFile(value);
    setTitle(value.name.replace(/\.[^.]+$/, ""));
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const document = await api.uploadDocument(file, title.trim(), token);
      setSuccess(
        `Uploaded ${document.title}, revision ${document.revision}. It is now available to the assistant.`,
      );
      onUploaded();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="panel editor document-upload">
      <div className="editor-heading">
        <div>
          <h2>Add a document</h2>
          <p className="small muted">
            Upload company knowledge for review and retrieval.
          </p>
        </div>
        <Upload size={21} />
      </div>
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
      <form onSubmit={upload}>
        <div className="form-grid">
          <label>
            <span>Document file</span>
            <input
              type="file"
              accept=".txt,.md,.pdf,.docx"
              onChange={(event) => selectFile(event.target.files?.[0])}
              disabled={pending}
              required
            />
          </label>
          <label>
            <span>Upload title</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
              disabled={pending}
              maxLength={250}
            />
          </label>
        </div>
        <div className="publish-footer">
          <p className="small muted">
            Text, Markdown, PDF or Word · max 10 MB (10,000,000 bytes).
            Extracted text is limited to 2 MB. Uploaded documents are labeled
            separately from official web sources.
          </p>
          <button
            className="button primary"
            disabled={!token.trim() || !file || !title.trim() || pending}
          >
            <Upload size={16} />
            {pending ? "Uploading and indexing…" : "Upload and ingest"}
          </button>
        </div>
      </form>
    </section>
  );
}
