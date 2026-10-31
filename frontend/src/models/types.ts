export interface Plan {
  id: string;
  name: string;
  capabilities: string[];
  max_users: number | null;
  price_minor: number | null;
  currency: string;
  billing_period: "month" | "year" | "once";
  billing_unit: "organization" | "seat";
  attributes: Record<string, string | number | boolean>;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  categories: string[];
  use_cases: string[];
  audiences: string[];
  plans: Plan[];
  is_synthetic: boolean;
  revision: number;
  status: "active" | "retired";
}

export interface Source {
  title: string;
  url: string;
  text?: string;
  document_id?: string;
  revision?: number;
  source_kind?: string;
  observed_at?: string;
}

export interface DocumentMetadata {
  id: string;
  title: string;
  source_url: string | null;
  revision: number;
  version: string;
  observed_at: string;
  source_kind: string;
  chunk_count: number;
}

export interface CompanyDocument extends DocumentMetadata {
  content: string;
}
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}
export interface ChatResponse {
  answer: string;
  thread_id: string;
  sources: Source[];
  warnings: string[];
}
export type ChatEvent =
  | { type: "session"; thread_id: string }
  | { type: "token"; text: string }
  | { type: "tool"; name: string; status: string }
  | ({ type: "done" } & ChatResponse)
  | { type: "error"; message: string };
export interface Health {
  status: string;
  mode: string;
  model_configured: boolean;
  integrations: Record<string, unknown>;
  model_provider?: string;
  model?: string;
  reasoning_level?: string;
  model_authentication?: string;
}
