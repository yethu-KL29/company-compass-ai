import type { Plan } from "../../models/types";
import { SpecificationEditor } from "./SpecificationEditor";
import { ListInput } from "../../components/ui/ListInput";

export function newPlan(): Plan {
  return {
    id: `plan-${crypto.randomUUID().slice(0, 8)}`,
    name: "New plan",
    capabilities: [],
    max_users: null,
    price_minor: null,
    currency: "INR",
    billing_period: "month",
    billing_unit: "organization",
    attributes: {},
  };
}

export function PlanEditor({
  plan,
  index,
  update,
  remove,
}: {
  plan: Plan;
  index: number;
  update: (plan: Plan) => void;
  remove: () => void;
}) {
  const digits =
    new Intl.NumberFormat("en", {
      style: "currency",
      currency: plan.currency || "INR",
    }).resolvedOptions().maximumFractionDigits ?? 2;

  return (
    <fieldset className="plan-editor">
      <legend>Plan {index + 1}</legend>
      <div className="form-grid">
        <label>
          <span>Plan name</span>
          <input
            value={plan.name}
            required
            onChange={(event) => update({ ...plan, name: event.target.value })}
          />
        </label>
        <label>
          <span>Plan ID</span>
          <input value={plan.id} readOnly />
        </label>
        <label>
          <span>Price ({plan.currency})</span>
          <input
            type="number"
            min="0"
            step={1 / 10 ** digits}
            value={
              plan.price_minor === null ? "" : plan.price_minor / 10 ** digits
            }
            placeholder="Unknown / quote only"
            onChange={(event) =>
              update({
                ...plan,
                price_minor:
                  event.target.value === ""
                    ? null
                    : Math.round(Number(event.target.value) * 10 ** digits),
              })
            }
          />
        </label>
        <label>
          <span>Currency</span>
          <select
            value={plan.currency}
            onChange={(event) =>
              update({ ...plan, currency: event.target.value })
            }
          >
            <option>INR</option>
            <option>USD</option>
            <option>EUR</option>
            <option>GBP</option>
          </select>
        </label>
        <label>
          <span>Billing period</span>
          <select
            value={plan.billing_period}
            onChange={(event) =>
              update({
                ...plan,
                billing_period: event.target.value as Plan["billing_period"],
              })
            }
          >
            <option value="month">Monthly</option>
            <option value="year">Yearly</option>
            <option value="once">One time</option>
          </select>
        </label>
        <label>
          <span>Billing unit</span>
          <select
            value={plan.billing_unit}
            onChange={(event) =>
              update({
                ...plan,
                billing_unit: event.target.value as Plan["billing_unit"],
              })
            }
          >
            <option value="organization">Organization</option>
            <option value="seat">Seat</option>
          </select>
        </label>
        <label>
          <span>Maximum users</span>
          <input
            type="number"
            min="1"
            step="1"
            value={plan.max_users ?? ""}
            placeholder="Unknown"
            onChange={(event) =>
              update({
                ...plan,
                max_users:
                  event.target.value === "" ? null : Number(event.target.value),
              })
            }
          />
        </label>
        <ListInput
          label="Included features (comma-separated)"
          value={plan.capabilities}
          onChange={(items) => update({ ...plan, capabilities: items })}
        />
      </div>
      <SpecificationEditor
        value={plan.attributes}
        onChange={(attributes) => update({ ...plan, attributes })}
      />
      <button type="button" className="text-button danger" onClick={remove}>
        Remove plan
      </button>
    </fieldset>
  );
}
