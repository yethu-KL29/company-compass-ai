import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Chat } from "../features/assistant/Chat";

afterEach(() => vi.unstubAllGlobals());

function ask(message = "**Keep my words literal**") {
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: message },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
}

function finishedResponse(answer: string) {
  return new Response(
    `data: ${JSON.stringify({
      type: "done",
      thread_id: "markdown-thread",
      answer,
      sources: [],
      warnings: [],
    })}\n\n`,
    { headers: { "Content-Type": "text/event-stream" } },
  );
}

it("renders streamed Markdown before completion and updates incomplete formatting", async () => {
  let controller: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(value) {
      controller = value;
    },
  });
  const send = (event: unknown) =>
    controller.enqueue(
      new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`),
    );
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));
  render(<Chat />);
  ask();
  await act(async () =>
    send({ type: "token", text: "## Catalog matches\n\n**Good" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Catalog matches" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
  await act(async () => {
    send({ type: "token", text: " choice**" });
    send({
      type: "done",
      thread_id: "markdown-thread",
      answer: "## Catalog matches\n\n**Good choice**",
      sources: [],
      warnings: [],
    });
    controller.close();
  });
  expect(
    await screen.findByText("Good choice", { selector: "strong" }),
  ).toBeInTheDocument();
});

it("renders completed tables, lists, fenced and inline code, and safe external links", async () => {
  const answer = [
    "## Compare plans",
    "",
    "**Recommended** for the team.",
    "",
    "- API included",
    "- Automation preferred",
    "",
    "| Plan | Price |",
    "| --- | --- |",
    "| Growth | INR 7500 |",
    "",
    "Use `plan_id` to identify the plan.",
    "",
    "```python",
    "print('hello')",
    "```",
    "",
    "[Official source](https://attoforce.ai/)",
  ].join("\n");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(finishedResponse(answer)));
  const view = render(<Chat />);
  ask();
  expect(
    await screen.findByRole("heading", { name: "Compare plans" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Recommended", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  const table = screen.getByRole("table");
  expect(
    within(table).getByRole("columnheader", { name: "Price" }),
  ).toBeInTheDocument();
  expect(
    within(table).getByRole("cell", { name: "INR 7500" }),
  ).toBeInTheDocument();
  expect(table.parentElement).toHaveClass("markdown-table-scroll");
  expect(screen.getByText("plan_id", { selector: "code" })).toBeInTheDocument();
  expect(view.container.querySelector("pre > code")).toHaveTextContent(
    "print('hello')",
  );
  expect(screen.getByRole("link", { name: "Official source" })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  expect(screen.getByRole("link", { name: "Official source" })).toHaveAttribute(
    "target",
    "_blank",
  );
  expect(screen.getByText("**Keep my words literal**")).toBeInTheDocument();
});

it("does not execute raw HTML or expose dangerous links and remote image loads", async () => {
  const answer =
    "<script>alert('bad')</script>\n\n<img src=x onerror=alert(1)>\n\n[Unsafe](javascript:alert%281%29)\n\n![Remote image](https://example.com/pixel.png)\n\n**Safe answer**";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(finishedResponse(answer)));
  const view = render(<Chat />);
  ask("Is this safe?");
  expect(
    await screen.findByText("Safe answer", { selector: "strong" }),
  ).toBeInTheDocument();
  expect(view.container.querySelector("script, img")).toBeNull();
  expect(view.container.querySelector('a[href^="javascript:"]')).toBeNull();
  expect(
    screen.queryByRole("link", { name: "Unsafe" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Remote image")).toBeInTheDocument();
});
