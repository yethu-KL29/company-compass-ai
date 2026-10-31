import { useEffect, useRef, type FormEvent } from "react";
import { Plus, Upload } from "lucide-react";
import type { Product } from "../../models/types";
import { newPlan, PlanEditor } from "./PlanEditor";
import { ListInput } from "../../components/ui/ListInput";

interface Props {
  product: Product;
  originalRevision: number | null;
  selected: string;
  pending: boolean;
  canPublish: boolean;
  update: <K extends keyof Product>(key: K, value: Product[K]) => void;
  onPublish: (event: FormEvent) => void;
  onCancel: () => void;
}

export function ProductEditor({
  product,
  originalRevision,
  selected,
  pending,
  canPublish,
  update,
  onPublish,
  onCancel,
}: Props) {
  const nameInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    nameInput.current?.focus();
    nameInput.current?.scrollIntoView?.({
      block: "center",
      behavior: "smooth",
    });
  }, [selected]);
  return (
    <form className="panel editor" onSubmit={onPublish}>
      <fieldset className="editor-fields" disabled={pending}>
        <div className="editor-heading">
          <h2>{originalRevision === null ? "Add product" : "Edit product"}</h2>
          <span className="badge">Synthetic demo</span>
        </div>
        <div className="form-grid">
          <label>
            <span>Product name</span>
            <input
              required
              ref={nameInput}
              value={product.name}
              onChange={(event) => update("name", event.target.value)}
            />
          </label>
          <label>
            <span>Product ID</span>
            <input
              required
              pattern="[a-zA-Z0-9_-]+"
              disabled={originalRevision !== null}
              value={product.id}
              placeholder="example-product"
              onChange={(event) => update("id", event.target.value)}
            />
          </label>
        </div>
        <label>
          <span>Description</span>
          <textarea
            required
            rows={3}
            value={product.description}
            onChange={(event) => update("description", event.target.value)}
          />
        </label>
        <div className="form-grid">
          <ListInput
            label="Categories (comma-separated)"
            value={product.categories}
            onChange={(items) => update("categories", items)}
            required
          />
          <ListInput
            label="Use cases (comma-separated)"
            value={product.use_cases}
            onChange={(items) => update("use_cases", items)}
          />
          <ListInput
            label="Intended audiences (comma-separated)"
            value={product.audiences}
            onChange={(items) => update("audiences", items)}
          />
          <label>
            <span>Publication status</span>
            <select
              value={product.status}
              onChange={(event) =>
                update("status", event.target.value as Product["status"])
              }
            >
              <option value="active">Active</option>
              <option value="retired">Retired</option>
            </select>
          </label>
        </div>
        <div className="editor-heading">
          <h3>Plans and entitlements</h3>
          <button
            type="button"
            className="button secondary compact"
            onClick={() => update("plans", [...product.plans, newPlan()])}
          >
            <Plus size={14} />
            Add plan
          </button>
        </div>
        {product.plans.map((plan, index) => (
          <PlanEditor
            key={`${selected}-${plan.id}`}
            plan={plan}
            index={index}
            update={(value) =>
              update(
                "plans",
                product.plans.map((item, position) =>
                  position === index ? value : item,
                ),
              )
            }
            remove={() =>
              update(
                "plans",
                product.plans.filter((_, position) => position !== index),
              )
            }
          />
        ))}
        <div className="publish-footer">
          <p className="small muted">
            {originalRevision === null
              ? "Creates the first published revision."
              : `Based on revision ${originalRevision}. Conflicting edits will be rejected.`}
          </p>
          <button type="button" className="button secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="button primary"
            disabled={pending || !canPublish || !product.plans.length}
          >
            <Upload size={16} />
            {pending
              ? "Saving…"
              : originalRevision === null
                ? "Create product"
                : "Save changes"}
          </button>
        </div>
      </fieldset>
    </form>
  );
}
