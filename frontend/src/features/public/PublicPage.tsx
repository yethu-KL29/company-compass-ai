import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, MessageCircle, MoveUpRight, X } from "lucide-react";
import { Chat } from "../assistant/Chat";
import "./public.css";

/** Public presentation only: conversation state and networking stay in Chat. */
export function PublicPage() {
  const [open, setOpen] = useState(false);
  const [visited, setVisited] = useState(false);
  const launcher = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) closeButton.current?.focus();
  }, [open]);

  function openAssistant() {
    setVisited(true);
    setOpen(true);
  }

  function closeAssistant() {
    setOpen(false);
    launcher.current?.focus();
  }

  return (
    <div className="public-site">
      <a className="skip-link" href="#public-content">
        Skip to content
      </a>
      <header className="public-nav">
        <a className="public-brand" href="/" aria-label="Attoforce home">
          <MoveUpRight size={25} aria-hidden="true" /> Attoforce
        </a>
        <nav aria-label="Public navigation">
          <a href="https://attoforce.ai/" target="_blank" rel="noreferrer">
            Explore Attoforce <ArrowUpRight size={15} aria-hidden="true" />
          </a>
          <a className="public-admin-link" href="/admin">
            Admin workspace
          </a>
        </nav>
      </header>
      <main id="public-content" tabIndex={-1}>
        <section className="public-hero" aria-labelledby="public-title">
          <div className="public-eyebrow">
            <span /> COMPANY COMPASS · ASSIGNMENT DEMO
          </div>
          <div className="public-hero-grid">
            <div className="public-hero-copy">
              <h1 id="public-title">
                A clearer
                <br />
                way forward.
              </h1>
              <p className="public-subtitle">
                Your needs. The right context.
                <br />A more informed choice.
              </p>
              <p className="public-description">
                Get to know Attoforce, describe what your team needs, and
                compare software options in one conversation.
              </p>
              <button className="public-start" onClick={openAssistant}>
                Start a conversation{" "}
                <ArrowUpRight size={19} aria-hidden="true" />
              </button>
            </div>
            <div
              className="public-context"
              aria-label="Company knowledge and your requirements inform product choices"
            >
              <p className="public-diagram-label">
                FROM CONTEXT TO A CLEARER CHOICE
              </p>
              <svg viewBox="0 0 500 240" fill="none" aria-hidden="true">
                <text x="12" y="12" fill="white" fontSize="13">
                  Your requirements
                </text>
                <text x="12" y="107" fill="white" fontSize="13">
                  Company knowledge
                </text>
                <text x="12" y="202" fill="white" fontSize="13">
                  Product catalog
                </text>
                <path
                  d="M12 25 H90 C180 25 130 120 260 120 H480"
                  stroke="var(--public-cyan)"
                />
                <path d="M12 120 H480" stroke="var(--public-violet)" />
                <path
                  d="M12 215 H90 C180 215 130 120 260 120 H480"
                  stroke="var(--public-orange)"
                />
                <circle cx="12" cy="25" r="4" fill="var(--public-cyan)" />
                <circle cx="12" cy="120" r="4" fill="var(--public-violet)" />
                <circle cx="12" cy="215" r="4" fill="var(--public-orange)" />
                <circle cx="315" cy="120" r="29" fill="#111" stroke="#6b6b6b" />
                <circle cx="315" cy="120" r="5" fill="white" />
                <circle cx="480" cy="120" r="5" fill="white" />
              </svg>
              <p className="public-outcome">
                A thoughtful
                <br />
                recommendation.
              </p>
              <p className="public-diagram-footnote">ASK. EXPLORE. COMPARE.</p>
            </div>
          </div>
        </section>
        <section className="public-guide" aria-label="What you can ask">
          <p>
            Start with a question.
            <br />
            <strong>Build on the answer.</strong>
          </p>
          <div>
            <span>01 / DISCOVER</span>
            <p>Understand the company through its documents.</p>
          </div>
          <div>
            <span>02 / FIND YOUR FIT</span>
            <p>Share your team size, budget, and must-have features.</p>
          </div>
          <div>
            <span>03 / COMPARE</span>
            <p>Explore the differences and ask follow-up questions.</p>
          </div>
        </section>
      </main>
      <footer className="public-footer">
        <span>Attoforce-inspired assignment experience.</span>
        <span>Catalog products are fictional demo offerings.</span>
      </footer>
      {visited && (
        <div
          id="public-assistant"
          className="public-chat-widget"
          role="dialog"
          aria-label="Attoforce assistant"
          hidden={!open}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              closeAssistant();
            }
          }}
        >
          <div className="public-widget-bar">
            <span>
              <MessageCircle size={18} aria-hidden="true" /> Attoforce assistant
            </span>
            <button
              ref={closeButton}
              aria-label="Close assistant"
              onClick={closeAssistant}
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>
          <Chat />
        </div>
      )}
      <button
        ref={launcher}
        className="public-chat-launcher"
        aria-label="Ask Attoforce"
        aria-expanded={open}
        aria-controls={visited ? "public-assistant" : undefined}
        onClick={open ? closeAssistant : openAssistant}
      >
        <MessageCircle size={22} aria-hidden="true" />
        <span>Ask Attoforce</span>
      </button>
    </div>
  );
}
