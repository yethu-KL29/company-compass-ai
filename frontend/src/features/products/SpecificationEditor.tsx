import { useState } from "react";
import { Plus, X } from "lucide-react";

type Value = string | number | boolean;
interface Row {
  id: string;
  name: string;
  value: string;
  type: "text" | "number" | "boolean";
}

export function SpecificationEditor({
  value,
  onChange,
}: {
  value: Record<string, Value>;
  onChange: (value: Record<string, Value>) => void;
}) {
  const [rows, setRows] = useState<Row[]>(() =>
    Object.entries(value).map(([name, item]) => ({
      id: crypto.randomUUID(),
      name,
      value: String(item),
      type:
        typeof item === "number"
          ? "number"
          : typeof item === "boolean"
            ? "boolean"
            : "text",
    })),
  );
  const [error, setError] = useState("");
  function commit(next: Row[]) {
    setRows(next);
    const complete = next.filter((row) => row.name.trim());
    if (
      new Set(complete.map((row) => row.name.trim())).size !== complete.length
    ) {
      setError("Use a different name for each specification.");
      return;
    }
    if (
      complete.some(
        (row) =>
          row.type === "number" &&
          (!row.value.trim() || !Number.isFinite(Number(row.value))),
      )
    ) {
      setError("Enter a valid number for numeric specifications.");
      return;
    }
    setError("");
    onChange(
      Object.fromEntries(
        complete.map((row) => [
          row.name.trim(),
          row.type === "number"
            ? Number(row.value)
            : row.type === "boolean"
              ? row.value === "true"
              : row.value,
        ]),
      ),
    );
  }
  function update(id: string, patch: Partial<Row>) {
    commit(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }
  return (
    <details className="specification-editor">
      <summary>Additional specifications</summary>
      <p className="small muted">
        Add useful plan limits or details, such as automation rules or
        deployment mode.
      </p>
      {rows.map((row, index) => (
        <div key={row.id} className="specification-row">
          <label>
            <span>Name</span>
            <input
              aria-label={`Specification name ${index + 1}`}
              value={row.name}
              onChange={(event) => update(row.id, { name: event.target.value })}
            />
          </label>
          <label>
            <span>Type</span>
            <select
              aria-label={`Specification type ${index + 1}`}
              value={row.type}
              onChange={(event) =>
                update(row.id, {
                  type: event.target.value as Row["type"],
                  value: event.target.value === "boolean" ? "true" : row.value,
                })
              }
            >
              <option value="text">Text</option>
              <option value="number">Number</option>
              <option value="boolean">Yes / no</option>
            </select>
          </label>
          <label>
            <span>Value</span>
            {row.type === "boolean" ? (
              <select
                aria-label={`Specification value ${index + 1}`}
                value={row.value}
                onChange={(event) =>
                  update(row.id, { value: event.target.value })
                }
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            ) : (
              <input
                aria-label={`Specification value ${index + 1}`}
                type={row.type === "number" ? "number" : "text"}
                value={row.value}
                onChange={(event) =>
                  update(row.id, { value: event.target.value })
                }
              />
            )}
          </label>
          <button
            type="button"
            className="icon-button"
            aria-label={`Remove specification ${index + 1}`}
            onClick={() => commit(rows.filter((item) => item.id !== row.id))}
          >
            <X size={15} />
          </button>
        </div>
      ))}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      <button
        type="button"
        className="button secondary compact"
        onClick={() =>
          commit([
            ...rows,
            { id: crypto.randomUUID(), name: "", value: "", type: "text" },
          ])
        }
      >
        <Plus size={14} />
        Add specification
      </button>
    </details>
  );
}
