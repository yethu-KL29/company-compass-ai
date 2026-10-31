import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "../App";

afterEach(() => vi.unstubAllGlobals());
it("offers exactly Assistant, Documents and Products navigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          url === "/api/health"
            ? {
                status: "ok",
                mode: "local",
                model_configured: false,
                integrations: {},
              }
            : [],
      }),
    ),
  );
  render(<App />);
  expect(
    within(screen.getByRole("navigation", { name: "Main navigation" }))
      .getAllByRole("button")
      .map((button) => button.textContent),
  ).toEqual(["Assistant", "Documents", "Products"]);
});

it("shares the in-memory admin token between Products and Documents", () => {
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    callback(0);
    return 1;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          url === "/api/health"
            ? {
                status: "ok",
                mode: "local",
                model_configured: false,
                integrations: {},
              }
            : [],
      }),
    ),
  );
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Products" }));
  fireEvent.change(screen.getByLabelText("Admin token"), {
    target: { value: "memory-only-token" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Documents" }));
  expect(screen.getByLabelText("Admin token")).toHaveValue("memory-only-token");
  expect(localStorage.getItem("admin-token")).toBeNull();
});
