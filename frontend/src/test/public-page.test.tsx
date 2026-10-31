import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PublicPage } from "../features/public/PublicPage";
import { api } from "../services/api";

afterEach(() => vi.restoreAllMocks());

it("opens a keyboard-accessible assistant without calling the agent on page load", () => {
  const stream = vi.spyOn(api, "chatStream");
  render(<PublicPage />);
  expect(screen.getByRole("link", { name: "Admin workspace" })).toHaveAttribute(
    "href",
    "/admin",
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  const launcher = screen.getByRole("button", { name: "Ask Attoforce" });
  fireEvent.click(launcher);
  expect(
    screen.getByRole("dialog", { name: "Attoforce assistant" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Close assistant" })).toHaveFocus();
  expect(launcher).toHaveAttribute("aria-expanded", "true");
  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(launcher).toHaveFocus();
  expect(stream).not.toHaveBeenCalled();
});

it("keeps the shared chat and server thread when minimized and reopened", async () => {
  const stream = vi
    .spyOn(api, "chatStream")
    .mockImplementation(async (_message, _thread, receive) => {
      receive({ type: "session", thread_id: "public-thread" });
      receive({ type: "token", text: "**SalesFlow** fits." });
      receive({
        type: "done",
        thread_id: "public-thread",
        answer: "**SalesFlow** fits.",
        sources: [],
        warnings: [],
      });
    });
  render(<PublicPage />);
  const launcher = screen.getByRole("button", { name: "Ask Attoforce" });
  fireEvent.click(launcher);
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "Find a CRM" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
  await waitFor(() =>
    expect(screen.getByText("SalesFlow").tagName).toBe("STRONG"),
  );
  fireEvent.click(screen.getByRole("button", { name: "Close assistant" }));
  fireEvent.click(launcher);
  expect(screen.getByText("SalesFlow")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "Compare it" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
  await waitFor(() => expect(stream).toHaveBeenCalledTimes(2));
  expect(stream.mock.calls[1][1]).toBe("public-thread");
});
