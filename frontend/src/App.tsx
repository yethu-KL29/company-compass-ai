import { useEffect, useState } from "react";
import {
  Compass,
  FileText,
  Layers3,
  MessageSquare,
  RefreshCw,
} from "lucide-react";
import { api, errorMessage } from "./services/api";
import type { Health, Product } from "./models/types";
import { Chat } from "./features/assistant/Chat";
import { DocumentsPage } from "./features/documents/DocumentsPage";
import { ProductsPage } from "./features/products/ProductsPage";
import "./admin.css";

type Page = "assistant" | "documents" | "products";
const pages = [
  { id: "assistant", label: "Assistant", icon: MessageSquare },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "products", label: "Products", icon: Layers3 },
] as const;

export function App() {
  const [page, setPage] = useState<Page>("assistant");
  const [token, setToken] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .products()
      .then((value) => {
        if (!cancelled) setProducts(value);
      })
      .catch((failure) => {
        if (!cancelled) setError(errorMessage(failure));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    api
      .health()
      .then((value) => {
        if (!cancelled) setHealth(value);
      })
      .catch(() => {
        if (!cancelled) setHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, [reload]);

  function navigate(next: Page) {
    setPage(next);
    requestAnimationFrame(() =>
      document.getElementById("main-content")?.focus(),
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="#assistant"
          onClick={(event) => {
            event.preventDefault();
            navigate("assistant");
          }}
        >
          <span className="brand-icon">
            <Compass size={26} />
          </span>
          <span>
            Company
            <br />
            <strong>Compass</strong>
          </span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={page === id ? "nav-item active" : "nav-item"}
              aria-current={page === id ? "page" : undefined}
              onClick={() => navigate(id)}
            >
              <Icon size={19} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="workspace-card">
            <span className="workspace-avatar">A</span>
            <div>
              <strong>Attoforce</strong>
              <span>Assignment workspace</span>
            </div>
          </div>
          <p>
            Explore with context.
            <br />
            Choose with confidence.
          </p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>{pages.find((item) => item.id === page)?.label}</strong>
          </div>
          <div className="topbar-actions">
            <span className="connection">
              <span className={`status-dot${health ? "" : " offline"}`} />
              {health
                ? health.mode === "local"
                  ? "Local demo"
                  : "Cloud mode"
                : "Backend unavailable"}
            </span>
            <button
              className="icon-button"
              aria-label="Refresh connection and products"
              onClick={() => setReload((value) => value + 1)}
            >
              <RefreshCw size={16} />
            </button>
            <span className="avatar" aria-label="Assignment workspace">
              CC
            </span>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          <div hidden={page !== "assistant"}>
            <Chat />
          </div>
          {page === "documents" && (
            <DocumentsPage token={token} onTokenChange={setToken} />
          )}
          {page === "products" && (
            <ProductsPage
              products={products}
              loading={loading}
              error={error}
              token={token}
              onTokenChange={setToken}
              onPublished={() => setReload((value) => value + 1)}
            />
          )}
          <footer className="workspace-footer">
            <span>COMPANY COMPASS</span>
            <p>
              Company evidence and synthetic catalog data are kept separate.
            </p>
            <span>Assignment edition</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
