import { ArrowUpRight } from "lucide-react";
import type { Source } from "../../models/types";

export function SourceLinks({ sources }: { sources: Source[] }) {
  const unique = [
    ...new Map(
      sources.map((source) => [
        source.document_id || source.url || source.title,
        source,
      ]),
    ).values(),
  ];
  return (
    <div className="sources">
      <span className="small muted">Sources</span>
      {unique.map((source) => (
        <div
          key={source.document_id || source.url || source.title}
          className="source-item"
        >
          {/^https?:\/\//.test(source.url) ? (
            <a href={source.url} target="_blank" rel="noopener noreferrer">
              {source.title}
              <ArrowUpRight size={12} />
            </a>
          ) : (
            <span className="source-title">{source.title}</span>
          )}
          {source.source_kind === "admin_edit" && (
            <span className="badge warning">Admin-edited</span>
          )}
          {source.source_kind === "admin_upload" && (
            <span className="badge outline">Uploaded document</span>
          )}
        </div>
      ))}
    </div>
  );
}
