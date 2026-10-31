import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { Chat } from "../features/assistant/Chat";
import { api } from "../services/api";

afterEach(() => vi.unstubAllGlobals());

function controlledStream() {
  let controller: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(value) {
      controller = value;
    },
  });
  return {
    response: new Response(body, {
      headers: { "Content-Type": "text/event-stream" },
    }),
    send(value: unknown) {
      controller.enqueue(
        new TextEncoder().encode(`data: ${JSON.stringify(value)}\n\n`),
      );
    },
    close() {
      controller.close();
    },
  };
}

function ask(value: string) {
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send question" }));
}

it("renders answer tokens before completion, then reuses only the server thread", async () => {
  const first = controlledStream();
  const second = controlledStream();
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(first.response)
    .mockResolvedValueOnce(second.response);
  vi.stubGlobal("fetch", fetch);
  render(<Chat />);
  ask("Recommend CRM");
  await act(async () => {
    first.send({ type: "session", thread_id: "thread-1" });
    first.send({ type: "token", text: "SalesFlow meets " });
  });
  expect(await screen.findByText("SalesFlow meets")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send question" })).toBeDisabled();
  await act(async () => {
    first.send({ type: "token", text: "your needs." });
    first.send({
      type: "done",
      thread_id: "thread-1",
      answer: "SalesFlow meets your needs.",
      sources: [],
      warnings: [],
    });
    first.close();
  });
  await waitFor(() =>
    expect(screen.getByLabelText("Your question")).toBeEnabled(),
  );
  ask("Compare it with WorkSuite");
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    message: "Compare it with WorkSuite",
    thread_id: "thread-1",
  });
  await act(async () => {
    second.send({
      type: "done",
      thread_id: "thread-1",
      answer: "Comparison from the catalog.",
      sources: [],
      warnings: [],
    });
    second.close();
  });
  expect(
    await screen.findByText("Comparison from the catalog."),
  ).toBeInTheDocument();
});

it("new chat cancels the active stream and clears its thread and turns", async () => {
  const stream = controlledStream();
  const next = controlledStream();
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(stream.response)
    .mockResolvedValueOnce(next.response);
  vi.stubGlobal("fetch", fetch);
  render(<Chat />);
  ask("Old question");
  await act(async () => {
    stream.send({ type: "session", thread_id: "old-thread" });
    stream.send({ type: "token", text: "Partial response" });
  });
  expect(await screen.findByText("Partial response")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "New chat" }));
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
  expect(screen.queryByText("Partial response")).not.toBeInTheDocument();
  ask("Fresh question");
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    message: "Fresh question",
  });
  await act(async () => {
    next.send({
      type: "done",
      thread_id: "new-thread",
      answer: "Fresh answer",
      sources: [],
      warnings: [],
    });
    next.close();
  });
});

it("keeps partial text and exposes a streaming error", async () => {
  const stream = controlledStream();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
  render(<Chat />);
  ask("Question");
  await act(async () => {
    stream.send({ type: "token", text: "Verified part" });
    stream.send({
      type: "error",
      message: "The model is unavailable. Please retry.",
    });
    stream.close();
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The model is unavailable",
  );
  expect(screen.getByText("Verified part")).toBeInTheDocument();
});

it("aborts a pending request when the chat unmounts", async () => {
  const stream = controlledStream();
  const fetch = vi.fn().mockResolvedValue(stream.response);
  vi.stubGlobal("fetch", fetch);
  const view = render(<Chat />);
  ask("Question");
  await act(async () => {
    stream.send({ type: "session", thread_id: "a" });
  });
  view.unmount();
  expect(fetch.mock.calls[0][1].signal.aborted).toBe(true);
});

it("decodes split UTF-8 and SSE frames without losing text", async () => {
  const bytes = new TextEncoder().encode(
    'data: {"type":"token","text":"₹ CRM"}\r\n\r\ndata: {"type":"done","thread_id":"t","answer":"₹ CRM","sources":[],"warnings":[]}\n\n',
  );
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let start = 0; start < bytes.length; start += 2)
        controller.enqueue(bytes.slice(start, start + 2));
      controller.close();
    },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));
  const onEvent = vi.fn();
  await api.chatStream(
    "Question",
    undefined,
    onEvent,
    new AbortController().signal,
  );
  expect(onEvent).toHaveBeenCalledWith({ type: "token", text: "₹ CRM" });
  expect(onEvent).toHaveBeenCalledWith(
    expect.objectContaining({ type: "done" }),
  );
});

it("reports an interrupted stream instead of accepting partial text as complete", async () => {
  const stream = controlledStream();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(stream.response));
  const result = api.chatStream(
    "Question",
    undefined,
    vi.fn(),
    new AbortController().signal,
  );
  stream.send({ type: "token", text: "Incomplete" });
  stream.close();
  await expect(result).rejects.toThrow(/interrupted/i);
});
