import { useEffect, useState } from "react";
import { api, errorMessage } from "../../services/api";
import type { DocumentMetadata } from "../../models/types";

export function useDocuments(refreshKey = 0) {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .documents()
      .then((items) => {
        if (!cancelled) setDocuments(items);
      })
      .catch((failure) => {
        if (!cancelled) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, refresh]);

  return {
    documents,
    loading,
    error,
    reload: () => setRefresh((value) => value + 1),
  };
}
