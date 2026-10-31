import type { ChatEvent } from "../models/types";

/** Decode SSE incrementally; network chunks need not align with UTF-8 or frames. */
export async function readChatStream(
  response: Response,
  onEvent: (event: ChatEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  if (!response.body) throw new Error("The response stream is unavailable.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let complete = false;
  const abort = () => {
    void reader.cancel().catch(() => {});
  };
  signal.addEventListener("abort", abort, { once: true });
  try {
    while (!complete) {
      signal.throwIfAborted();
      const { done, value } = await reader.read();
      signal.throwIfAborted();
      buffer += decoder.decode(value, { stream: !done });
      let boundary: RegExpExecArray | null;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const data = frame
          .split(/\r?\n/)
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue; // Heartbeats and SSE comments carry no answer data.
        let event: ChatEvent;
        try {
          event = JSON.parse(data) as ChatEvent;
        } catch {
          throw new Error("The server returned an invalid response stream.");
        }
        if (event.type === "error") throw new Error(event.message);
        onEvent(event);
        if (event.type === "done") {
          complete = true;
          break;
        }
      }
      if (done) break;
    }
    if (!complete)
      throw new Error("The response was interrupted. Please try again.");
  } finally {
    signal.removeEventListener("abort", abort);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
