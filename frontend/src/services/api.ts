import type {
  ChatEvent,
  Health,
  Product,
  CompanyDocument,
  DocumentMetadata,
} from "../models/types";
import { readChatStream } from "./chatStream";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item: { msg?: string }) => item.msg || "Invalid value")
              .join("; ")
          : `Request failed (${response.status}). Please try again.`;
    throw new ApiError(message, response.status);
  }
  return body as T;
}

const post = (body: unknown, token?: string): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
  headers: token ? { "X-Admin-Token": token } : {},
});

export const api = {
  health: () => request<Health>("/health"),
  products: () => request<Product[]>("/products"),
  documents: () => request<DocumentMetadata[]>("/documents"),
  uploadDocument: (file: File, title: string, token: string) => {
    const body = new FormData();
    body.append("file", file);
    body.append("title", title);
    return request<CompanyDocument>("/admin/documents/upload", {
      method: "POST",
      body,
      headers: { "X-Admin-Token": token },
    });
  },
  document: (id: string) =>
    request<CompanyDocument>(`/documents/${encodeURIComponent(id)}`),
  updateDocument: (
    id: string,
    title: string,
    content: string,
    expected_revision: number,
    token: string,
  ) =>
    request<CompanyDocument>(`/admin/documents/${encodeURIComponent(id)}`, {
      ...post({ title, content, expected_revision }, token),
      method: "PUT",
    }),
  chatStream: async (
    message: string,
    threadId: string | undefined,
    onEvent: (event: ChatEvent) => void,
    signal: AbortSignal,
  ): Promise<void> => {
    const response = await fetch("/api/chat/stream", {
      ...post({ message, thread_id: threadId }),
      signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new ApiError(
        typeof body?.detail === "string"
          ? body.detail
          : `Request failed (${response.status}). Please try again.`,
        response.status,
      );
    }
    await readChatStream(response, onEvent, signal);
  },
  publish: (
    product: Product,
    expected_revision: number | null,
    token: string,
  ) =>
    request<Product>(
      "/admin/products",
      post({ product, expected_revision }, token),
    ),
};

export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
