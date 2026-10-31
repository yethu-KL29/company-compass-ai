import type { Product } from "../../models/types";
import { formatPrice, readable } from "../../utils/format";
import { Pencil } from "lucide-react";

export function ProductDetails({
  product,
  onEdit,
}: {
  product: Product;
  onEdit: () => void;
}) {
  return (
    <article className="panel editor product-details">
      <div className="editor-heading">
        <h2>{product.name}</h2>
        <button className="button secondary compact" onClick={onEdit}>
          <Pencil size={14} /> Edit product
        </button>
        <span className="badge">Synthetic demo</span>
      </div>
      <p className="muted">{product.description}</p>
      <dl className="product-facts">
        <div>
          <dt>Categories</dt>
          <dd>{product.categories.map(readable).join(", ")}</dd>
        </div>
        <div>
          <dt>Use cases</dt>
          <dd>
            {product.use_cases.map(readable).join(", ") || "Not specified"}
          </dd>
        </div>
        <div>
          <dt>Intended users</dt>
          <dd>
            {product.audiences.map(readable).join(", ") || "Not specified"}
          </dd>
        </div>
        <div>
          <dt>Publication</dt>
          <dd>
            Revision {product.revision} · {product.status}
          </dd>
        </div>
      </dl>
      <h3>Plans</h3>
      <div className="product-plan-grid">
        {product.plans.map((plan) => (
          <section key={plan.id} className="product-plan">
            <h3>{plan.name}</h3>
            <strong>{formatPrice(plan)}</strong>
            <p className="small muted">
              {plan.max_users === null
                ? "User limit not specified"
                : `Up to ${plan.max_users} users`}
            </p>
            <p className="small">
              {plan.capabilities.map(readable).join(" · ") ||
                "No included capabilities listed"}
            </p>
            {Object.entries(plan.attributes).map(([name, value]) => (
              <p key={name} className="small muted">
                {readable(name)}: {String(value)}
              </p>
            ))}
          </section>
        ))}
      </div>
    </article>
  );
}
