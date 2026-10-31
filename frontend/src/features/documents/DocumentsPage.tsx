import { useState } from "react";
import { AdminAccess } from "../../components/ui/AdminAccess";
import { Documents } from "./DocumentLibrary";
import { DocumentManager } from "./DocumentManager";
import { DocumentUpload } from "./DocumentUpload";

export function DocumentsPage({
  token,
  onTokenChange,
}: {
  token: string;
  onTokenChange: (value: string) => void;
}) {
  const [refresh, setRefresh] = useState(0);
  return (
    <section>
      <div className="section-intro">
        <div>
          <div className="eyebrow">Company knowledge</div>
          <h1>Documents</h1>
          <p className="muted">
            Read published knowledge, upload new sources and keep their contents
            current.
          </p>
        </div>
      </div>
      <AdminAccess token={token} onChange={onTokenChange} />
      <DocumentUpload
        token={token}
        onUploaded={() => setRefresh((value) => value + 1)}
      />
      <Documents refreshKey={refresh} showHeading={false} />
      <DocumentManager token={token} refreshKey={refresh} />
    </section>
  );
}
