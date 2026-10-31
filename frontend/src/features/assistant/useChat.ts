import { useEffect, useRef, useState } from "react";
import type { ChatEvent, ChatMessage, ChatResponse } from "../../models/types";
import { api, errorMessage } from "../../services/api";

interface Turn extends ChatMessage {
  id: string;
  response?: ChatResponse;
}

export function useChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const thread = useRef<string | undefined>(undefined);
  const active = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      active.current?.abort();
      active.current = null;
    },
    [],
  );

  function newChat() {
    active.current?.abort();
    active.current = null;
    thread.current = undefined;
    setTurns([]);
    setPending(false);
    setStatus("");
    setError("");
  }

  async function send(message: string) {
    if (active.current) return;
    const controller = new AbortController();
    active.current = controller;
    const answerId = crypto.randomUUID();
    setTurns((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", content: message },
      { id: answerId, role: "assistant", content: "" },
    ]);
    setPending(true);
    setStatus("Thinking…");
    setError("");

    function receive(event: ChatEvent) {
      if (controller.signal.aborted || active.current !== controller) return;
      if (event.type === "session") thread.current = event.thread_id;
      if (event.type === "tool") {
        setStatus(
          event.name === "company_rag"
            ? "Checking company documents…"
            : "Inspecting the product catalog…",
        );
      }
      if (event.type === "token") {
        setStatus("Writing the answer…");
        setTurns((previous) =>
          previous.map((turn) =>
            turn.id === answerId
              ? { ...turn, content: turn.content + event.text }
              : turn,
          ),
        );
      }
      if (event.type === "done") {
        thread.current = event.thread_id;
        setTurns((previous) =>
          previous.map((turn) =>
            turn.id === answerId
              ? { ...turn, content: event.answer, response: event }
              : turn,
          ),
        );
      }
    }

    try {
      await api.chatStream(message, thread.current, receive, controller.signal);
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure));
    } finally {
      if (active.current === controller) {
        active.current = null;
        setPending(false);
        setStatus("");
      }
    }
  }

  return { turns, pending, status, error, send, newChat };
}
