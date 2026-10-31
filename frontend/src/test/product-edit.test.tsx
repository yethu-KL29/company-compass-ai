import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ProductsPage } from "../features/products/ProductsPage";
import type { Product } from "../models/types";

const product: Product = {
  id: "sales",
  name: "Sales Demo",
  description: "Synthetic CRM",
  categories: ["crm"],
  use_cases: ["sales_pipeline"],
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
  is_synthetic: true,
  revision: 3,
  status: "active",
};

afterEach(() => vi.unstubAllGlobals());

function page(token = "admin-token") {
  const published = vi.fn();
  render(
    <ProductsPage
      products={[product]}
      token={token}
      onTokenChange={() => {}}
      onPublished={published}
    />,
  );
  return published;
}

it("edits selected product details in place and cancels without saving a draft", () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  page();
  expect(screen.queryByLabelText("Product name")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "View Sales Demo" }));
  fireEvent.click(screen.getByRole("button", { name: "Edit product" }));
  expect(screen.getByLabelText("Product name")).toHaveValue("Sales Demo");
  expect(screen.getByLabelText("Product name")).toHaveFocus();
  expect(screen.getByLabelText("Product ID")).toBeDisabled();
  expect(
    screen.queryByRole("heading", { name: "Sales Demo" }),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Product name"), {
    target: { value: "Unsaved name" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(
    screen.getByRole("heading", { name: "Sales Demo" }),
  ).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Edit product" }));
  expect(screen.getByLabelText("Product name")).toHaveValue("Sales Demo");
});

it("saves a card edit with the original revision and immediately shows returned details", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(
        JSON.stringify({ ...product, name: "Sales Updated", revision: 4 }),
        { status: 200 },
      ),
    );
  vi.stubGlobal("fetch", fetch);
  const published = page();
  fireEvent.click(screen.getByRole("button", { name: "Edit Sales Demo" }));
  fireEvent.change(screen.getByLabelText("Product name"), {
    target: { value: "Sales Updated" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(
    await screen.findByRole("heading", { name: "Sales Updated" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Revision 4 · active")).toBeInTheDocument();
  expect(screen.queryByLabelText("Product name")).not.toBeInTheDocument();
  expect(published).toHaveBeenCalledOnce();
  const [url, options] = fetch.mock.calls[0];
  expect(url).toBe("/api/admin/products");
  expect(options.headers["X-Admin-Token"]).toBe("admin-token");
  expect(JSON.parse(options.body).expected_revision).toBe(3);
  expect(JSON.parse(options.body).product.id).toBe("sales");
});

it("opens blank creation explicitly and requires an admin token to save", () => {
  page("");
  fireEvent.click(screen.getByRole("button", { name: "Edit Sales Demo" }));
  expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Add product" }));
  expect(screen.getByLabelText("Product name")).toHaveValue("");
  expect(screen.getByLabelText("Product ID")).not.toBeDisabled();
  expect(screen.getByRole("button", { name: "Create product" })).toBeDisabled();
});

it("locks the current edit while saving and keeps unsaved values after a conflict", async () => {
  let finish!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    ),
  );
  page();
  fireEvent.click(screen.getByRole("button", { name: "Edit Sales Demo" }));
  fireEvent.change(screen.getByLabelText("Product name"), {
    target: { value: "Unsaved name" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(screen.getByRole("button", { name: "Add product" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Edit Sales Demo" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  expect(screen.getByLabelText("Product name")).toBeDisabled();
  finish(
    new Response(
      JSON.stringify({ detail: "Catalog changed. Reload and retry." }),
      { status: 409 },
    ),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Catalog changed");
  expect(screen.getByLabelText("Product name")).toHaveValue("Unsaved name");
  expect(
    screen.getByRole("button", { name: "Save changes" }),
  ).not.toBeDisabled();
});
