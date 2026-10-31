import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { AdminAccess } from "../../components/ui/AdminAccess";
import { api, errorMessage } from "../../services/api";
import type { Product } from "../../models/types";
import { ProductEditor } from "./ProductEditor";
import { ProductDetails } from "./ProductDetails";
import { newPlan } from "./PlanEditor";
import { ProductCard } from "./ProductCard";

function newProduct(): Product {
  return {
    id: "",
    name: "",
    description: "",
    categories: [],
    use_cases: [],
    audiences: [],
    plans: [newPlan()],
    is_synthetic: true,
    revision: 1,
    status: "active",
  };
}
interface Props {
  products: Product[];
  loading?: boolean;
  error?: string;
  token: string;
  onTokenChange: (value: string) => void;
  onPublished: () => void;
}

export function ProductsPage({
  products,
  loading = false,
  error: loadError = "",
  token,
  onTokenChange,
  onPublished,
}: Props) {
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState<Product>(newProduct);
  const [selected, setSelected] = useState("");
  const [originalRevision, setOriginalRevision] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState(false);
  const [savedProduct, setSavedProduct] = useState<Product | null>(null);
  const shown = products.filter((item) =>
    item.name.toLowerCase().includes(query.toLowerCase()),
  );
  const published = currentProduct(selected);

  function currentProduct(id: string) {
    const fetched = products.find((item) => item.id === id);
    return savedProduct?.id === id &&
      savedProduct.revision >= (fetched?.revision ?? 0)
      ? savedProduct
      : fetched;
  }
  function choose(id: string, edit = false) {
    const existing = currentProduct(id);
    setSelected(id);
    setProduct(existing ? structuredClone(existing) : newProduct());
    setOriginalRevision(existing?.revision ?? null);
    setError("");
    setSuccess("");
    setEditing(edit);
  }
  function cancel() {
    choose(selected);
  }
  function update<K extends keyof Product>(key: K, value: Product[K]) {
    setProduct((previous) => ({ ...previous, [key]: value }));
  }
  async function publish(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSuccess("");
    try {
      const saved = await api.publish(product, originalRevision, token);
      setProduct(saved);
      setSelected(saved.id);
      setOriginalRevision(saved.revision);
      setSavedProduct(saved);
      setEditing(false);
      setSuccess(`Published ${saved.name}, revision ${saved.revision}.`);
      onPublished();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setPending(false);
    }
  }

  return (
    <section>
      <div className="section-intro">
        <div>
          <div className="eyebrow">Published software offerings</div>
          <h1>Products</h1>
          <p className="muted">
            View current product details and manage their plans and
            capabilities. Ask the assistant for recommendations and comparisons.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={pending}
          onClick={() => choose("", true)}
        >
          <Plus size={16} />
          Add product
        </button>
      </div>
      <AdminAccess token={token} onChange={onTokenChange} />
      <label className="product-finder">
        <span>Find a product by name</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search current products…"
        />
      </label>
      {(loadError || error) && (
        <p className="notice error" role="alert">
          {error || loadError}
        </p>
      )}
      {success && (
        <p className="notice success" role="status">
          {success}
        </p>
      )}
      {loading && (
        <p role="status" className="notice">
          Loading products…
        </p>
      )}
      <div className="management-product-grid">
        {shown.map((item) => (
          <ProductCard
            key={item.id}
            product={currentProduct(item.id) ?? item}
            selected={selected === item.id}
            disabled={pending}
            onView={() => choose(item.id)}
            onEdit={() => choose(item.id, true)}
          />
        ))}
      </div>
      {!loading && !shown.length && (
        <p className="notice">No products match that name.</p>
      )}
      {published && !editing && (
        <ProductDetails
          product={published}
          onEdit={() => choose(selected, true)}
        />
      )}
      {editing && (
        <ProductEditor
          product={product}
          originalRevision={originalRevision}
          selected={selected}
          pending={pending}
          canPublish={!!token.trim()}
          update={update}
          onPublish={publish}
          onCancel={cancel}
        />
      )}
    </section>
  );
}
