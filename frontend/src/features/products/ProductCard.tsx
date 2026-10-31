import { Layers3, Pencil } from "lucide-react";
import type { Product } from "../../models/types";

interface Props {
  product: Product;
  selected: boolean;
  disabled: boolean;
  onView: () => void;
  onEdit: () => void;
}

export function ProductCard({
  product,
  selected,
  disabled,
  onView,
  onEdit,
}: Props) {
  return (
    <article
      className={`management-product-card panel ${selected ? "selected" : ""}`}
    >
      <button
        className="product-card-view"
        disabled={disabled}
        aria-label={`View ${product.name}`}
        aria-pressed={selected}
        onClick={onView}
      >
        <span className="product-icon">
          <Layers3 size={21} />
        </span>
        <strong>{product.name}</strong>
        <span className="small muted">
          {product.plans.length} plans · revision {product.revision} ·{" "}
          {product.status}
        </span>
        <span className="badge">Synthetic demo</span>
      </button>
      <button
        className="button secondary compact"
        aria-label={`Edit ${product.name}`}
        disabled={disabled}
        onClick={onEdit}
      >
        <Pencil size={14} /> Edit
      </button>
    </article>
  );
}
