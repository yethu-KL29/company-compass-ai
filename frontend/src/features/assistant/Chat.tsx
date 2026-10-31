import { useRef, useState, type FormEvent } from "react";
import { ArrowUp, ArrowUpRight, Compass, Sparkles } from "lucide-react";
import { SourceLinks } from "./SourceLinks";
import { useChat } from "./useChat";
import { MarkdownMessage } from "./MarkdownMessage";

const suggestions = [
  "What does Attoforce do?",
  "Find a CRM for a ten-person team",
  "Compare SalesFlow and WorkSuite Sales",
  "Which option is better for a growing sales team?",
];

export function Chat() {
  const {
    turns,
    pending,
    status,
    error,
    send: sendMessage,
    newChat,
  } = useChat();
  const [question, setQuestion] = useState("");
  const input = useRef<HTMLTextAreaElement>(null);

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = question.trim();
    if (!message || pending) return;
    setQuestion("");
    await sendMessage(message);
    input.current?.focus();
  }

  function selectSuggestion(value: string) {
    setQuestion(value);
    input.current?.focus();
  }

  return (
    <section className="assistant-layout">
      <div className="chat-panel panel">
        <div className="panel-heading">
          <div className="icon-square">
            <Sparkles size={18} />
          </div>
          <div>
            <h2>Your company copilot</h2>
            <p className="small muted">
              Company answers. Thoughtful product choices.
            </p>
          </div>
          <button
            className="new-chat"
            onClick={() => {
              newChat();
              setQuestion("");
              input.current?.focus();
            }}
          >
            New chat
          </button>
        </div>
        <div
          className="conversation"
          role="log"
          aria-label="Conversation"
          aria-live="polite"
          aria-busy={pending}
        >
          {turns.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">
                <Compass size={32} />
              </div>
              <h3>
                A little context.
                <br />A clearer direction.
              </h3>
              <p className="muted">
                Ask about the company, describe what your team needs, or explore
                the demo software catalog.
              </p>
              <div className="suggestions">
                {suggestions.map((text) => (
                  <button key={text} onClick={() => selectSuggestion(text)}>
                    {text}
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((turn) => (
            <article key={turn.id} className={`message ${turn.role}`}>
              <span className="message-label">
                {turn.role === "user" ? "You" : "Company Compass"}
              </span>
              {turn.role === "assistant" ? (
                <MarkdownMessage content={turn.content} />
              ) : (
                <p>{turn.content}</p>
              )}
              {turn.response?.warnings.map((warning) => (
                <p key={warning} className="notice warning small">
                  {warning}
                </p>
              ))}
              {!!turn.response?.sources.length && (
                <SourceLinks sources={turn.response.sources} />
              )}
            </article>
          ))}
          {pending && (
            <p className="thinking" role="status">
              <span className="pulse" />
              {status}
            </p>
          )}
        </div>
        <form className="composer" onSubmit={send}>
          {error && (
            <p className="notice error" role="alert">
              {error}
            </p>
          )}
          <label className="sr-only" htmlFor="question">
            Your question
          </label>
          <div className="composer-input">
            <textarea
              ref={input}
              id="question"
              rows={2}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What would you like to know or find?"
              maxLength={2000}
              disabled={pending}
            />
            <button
              className="send-button"
              aria-label="Send question"
              disabled={pending || !question.trim()}
            >
              <ArrowUp size={20} />
            </button>
          </div>
          <p className="small muted">
            Company answers include sources when available. Catalog products are
            fictional demo offerings.
          </p>
        </form>
      </div>
    </section>
  );
}
