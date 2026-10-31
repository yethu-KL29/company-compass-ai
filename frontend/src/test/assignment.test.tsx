import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Chat } from "../features/assistant/Chat";
import { ProductsPage } from "../features/products/ProductsPage";
import { formatPrice } from "../utils/format";
import { ListInput } from "../components/ui/ListInput";
import { PlanEditor, newPlan } from "../features/products/PlanEditor";
import type { Product } from "../models/types";

afterEach(() => vi.unstubAllGlobals());

describe("assignment customer and admin behavior", () => {
  it("uses the backend's one-time price and billing-unit vocabulary", () => {
    const update = vi.fn();
    render(
      <PlanEditor
        plan={newPlan()}
        index={0}
        update={update}
        remove={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Billing period"), {
      target: { value: "once" },
    });
    expect(update).toHaveBeenLastCalledWith(
      expect.objectContaining({ billing_period: "once" }),
    );
    expect(screen.getByLabelText("Billing unit")).not.toHaveTextContent("Unit");
  });
  it("preserves a trailing comma while entering multiple required features", () => {
    const update = vi.fn();
    render(<ListInput label="Capabilities" value={[]} onChange={update} />);
    fireEvent.change(screen.getByLabelText("Capabilities"), {
      target: { value: "api," },
    });
    expect(screen.getByLabelText("Capabilities")).toHaveValue("api,");
    fireEvent.change(screen.getByLabelText("Capabilities"), {
      target: { value: "api, automation" },
    });
    expect(update).toHaveBeenLastCalledWith(["api", "automation"]);
  });
  it("keeps unknown prices distinct from free prices and retains billing basis", () => {
    expect(
      formatPrice({
        price_minor: null,
        currency: "INR",
        billing_period: "month",
        billing_unit: "organization",
      }),
    ).toBe("Contact for pricing");
    expect(
      formatPrice({
        price_minor: 0,
        currency: "INR",
        billing_period: "month",
        billing_unit: "seat",
      }),
    ).toContain("0");
    expect(
      formatPrice({
        price_minor: 900000,
        currency: "INR",
        billing_period: "month",
        billing_unit: "organization",
      }),
    ).toContain("organization");
  });

  it("submits a real chat request and exposes backend failure without invented answers", async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Model not configured" }), {
        status: 503,
      }),
    );
    vi.stubGlobal("fetch", fetch);
    render(<Chat />);
    expect(screen.getByLabelText("Your question")).toHaveAttribute(
      "maxlength",
      "2000",
    );
    fireEvent.change(screen.getByLabelText("Your question"), {
      target: { value: "Find a CRM with API access" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send question" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("Model not configured");
    expect(fetch).toHaveBeenCalledWith(
      "/api/chat/stream",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("sends admin edits with authentication and the original revision", async () => {
    const product: Product = {
      id: "sales",
      name: "Sales Demo",
      description: "Synthetic CRM",
      categories: ["CRM"],
      use_cases: ["sales"],
      audiences: ["teams"],
      plans: [
        {
          id: "starter",
          name: "Starter",
          capabilities: ["api"],
          max_users: 10,
          price_minor: 900000,
          currency: "INR",
          billing_period: "month",
          billing_unit: "organization",
          attributes: {},
        },
      ],
      is_synthetic: true as const,
      revision: 3,
      status: "active" as const,
    };
    const fetch = vi.fn((url: string, options?: RequestInit) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () =>
          url === "/api/documents"
            ? []
            : { ...JSON.parse(options?.body as string).product, revision: 4 },
      }),
    );
    vi.stubGlobal("fetch", fetch);
    render(
      <ProductsPage
        products={[product]}
        token="test-token"
        onTokenChange={() => {}}
        onPublished={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit Sales Demo" }));
    fireEvent.change(screen.getByLabelText("Product name"), {
      target: { value: "Sales Updated" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByText("Published Sales Updated, revision 4.");
    const options = fetch.mock.calls.find(
      ([url]) => url === "/api/admin/products",
    )![1]!;
    expect((options.headers as Record<string, string>)["X-Admin-Token"]).toBe(
      "test-token",
    );
    expect(JSON.parse(options.body as string).expected_revision).toBe(3);
    expect(JSON.parse(options.body as string).product.name).toBe(
      "Sales Updated",
    );
  });
});
