import { useEffect, useRef, useState } from "react";
import useChat from "../hooks/useChat.js";

export default function ChatPanel({ caseId, stateSnapshot }) {
  const ready = !!stateSnapshot?.result;
  const { messages, status, send } = useChat({ caseId, stateSnapshot });
  const [input, setInput] = useState("");
  const [starters, setStarters] = useState([]);
  const scrollRef = useRef(null);

  // Fetch starter questions when the case-pack becomes available
  useEffect(() => {
    const cp = stateSnapshot?.result?.case_pack;
    if (!cp) { setStarters([]); return; }
    fetch("/api/chat/starters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_pack: cp }),
    })
      .then((r) => r.json())
      .then((d) => setStarters(d.questions ?? []))
      .catch(() => setStarters([]));
  }, [stateSnapshot?.result?.case_pack]);

  // Auto-scroll on new content
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const onSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    send(input.trim());
    setInput("");
  };

  const onStarter = (q) => {
    send(q);
  };

  return (
    <aside className="chat-panel">
      <div className="chat-header">
        <div className="chat-title">Bill Exceptions Assistant</div>
        <div className="chat-subtitle">
          {ready ? "Ask about this case" : "Run screening to start a conversation"}
        </div>
      </div>

      <div className="chat-messages" ref={scrollRef}>
        {messages.length === 0 && ready && (
          <div className="chat-empty">
            <p className="chat-empty-line">I can explain the screening result, walk through the rules that fired, or surface case data.</p>
            {starters.length > 0 && (
              <div className="chat-starters">
                {starters.map((q, i) => (
                  <button key={i} className="chat-starter" onClick={() => onStarter(q)}>
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.length === 0 && !ready && (
          <div className="chat-empty chat-empty-muted">
            <p>Pick a case and click <strong>Run Screening</strong> — when the screening finishes, I'll be ready.</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg-${m.role} ${m.error ? "chat-msg-error" : ""} ${m.partial ? "chat-msg-partial" : ""}`}>
            <div className="chat-msg-body">{m.content}</div>
          </div>
        ))}

        {status === "streaming" && messages[messages.length - 1]?.role === "user" && (
          <div className="chat-msg chat-msg-assistant chat-msg-partial">
            <div className="chat-msg-body chat-thinking">Thinking…</div>
          </div>
        )}
      </div>

      <form className="chat-input-row" onSubmit={onSubmit}>
        <input
          className="chat-input"
          placeholder={ready ? "Ask a question…" : "Run screening first"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!ready || status === "streaming"}
        />
        <button
          className="chat-send"
          type="submit"
          disabled={!ready || status === "streaming" || !input.trim()}
        >
          Send
        </button>
      </form>
    </aside>
  );
}
