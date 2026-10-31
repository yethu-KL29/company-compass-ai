import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Application } from "../Application";

vi.mock("../App", () => ({ App: () => <div>Admin workspace</div> }));
vi.mock("../features/public/PublicPage", () => ({
  PublicPage: () => <div>Public assistant</div>,
}));

afterEach(() => window.history.replaceState({}, "", "/"));

it("opens the user experience at the root", () => {
  window.history.replaceState({}, "", "/");
  render(<Application />);
  expect(screen.getByText("Public assistant")).toBeInTheDocument();
  expect(screen.queryByText("Admin workspace")).not.toBeInTheDocument();
});

it.each(["/admin", "/admin/"])("keeps the existing workspace at %s", (path) => {
  window.history.replaceState({}, "", path);
  render(<Application />);
  expect(screen.getByText("Admin workspace")).toBeInTheDocument();
});
