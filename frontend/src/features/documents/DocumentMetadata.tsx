import { ArrowUpRight } from "lucide-react";
import type { DocumentMetadata as Metadata } from "../../models/types";

export function DocumentMetadata({ document }: { document: Metadata }) {
  const date = new Date(document.observed_at);
  return (
    <div className="document-metadata">
      <span
        className={`badge ${document.source_kind === "admin_edit" ? "warning" : "outline"}`}
      >
        {document.source_kind === "admin_edit"
          ? "Admin-edited"
          : document.source_kind === "admin_upload"
            ? "Uploaded document"
            : "Source document"}
      </span>
      <dl>
        <div>
          <dt>Document ID</dt>
          <dd>
            <code>{document.id}</code>
          </dd>
        </div>
        <div>
          <dt>Revision</dt>
          <dd>{document.revision}</dd>
        </div>
        <div>
          <dt>Source type</dt>
          <dd>
            {document.source_kind === "admin_edit"
              ? "Admin-edited"
              : document.source_kind.replaceAll("_", " ")}
          </dd>
        </div>
        <div>
          <dt>Observed</dt>
          <dd>
            {Number.isNaN(date.valueOf())
              ? document.observed_at
              : date.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt>Indexed chunks</dt>
          <dd>{document.chunk_count}</dd>
        </div>
      </dl>
      {document.source_url && /^https?:\/\//.test(document.source_url) && (
        <a
          href={document.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="document-source"
        >
          {document.source_url}
          <ArrowUpRight size={13} />
        </a>
      )}
      {document.source_kind === "admin_edit" && (
        <p className="small muted">
          This version was edited by an administrator. Any source URL identifies
          its origin, not verification of the edited text.
        </p>
      )}
    </div>
  );
}
