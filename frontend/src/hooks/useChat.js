import { useCallback, useEffect, useRef, useState } from "react";
import { openChatSocket } from "../api/websocket.js";

/**
 * Chat hook bound to a single screening case. Manages:
 *   - WebSocket lifecycle (open once per case_id, close on case change)
 *   - Conversation state (messages list, current streaming response)
 *   - Streaming chunks → typewriter effect in the assistant message
 *
 * Inputs:
 *   caseId         — current case being chatted about
 *   stateSnapshot  — { case, trace, result } passed to the backend on init
 *
 * Outputs:
 *   messages    — list of {role:'user'|'assistant', content:string, partial?:boolean}
 *   status      — 'idle' | 'streaming' | 'error'
 *   send(text)  — send a user message
 *   reset()     — clear local messages and ask backend to reset conversation
 */
export default function useChat({ caseId, stateSnapshot }) {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle");      // idle | streaming | error
  const sockRef     = useRef(null);
  const lastCaseRef = useRef(null);

  // Open/refresh socket when case changes
  useEffect(() => {
    if (!caseId || !stateSnapshot?.result) return;

    // close existing socket
    sockRef.current?.close?.();
    setMessages([]);
    setStatus("idle");

    const sock = openChatSocket({
      onEvent: (evt) => {
        if (evt.type === "chunk") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant" && last.partial) {
              return [...prev.slice(0, -1), { ...last, content: last.content + evt.text }];
            }
            return [...prev, { role: "assistant", content: evt.text, partial: true }];
          });
        } else if (evt.type === "done") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === "assistant" && last.partial) {
              return [...prev.slice(0, -1), { ...last, partial: false }];
            }
            return prev;
          });
          setStatus("idle");
        } else if (evt.type === "error") {
          setMessages((prev) => [...prev, { role: "assistant", content: `⚠ ${evt.message}`, error: true }]);
          setStatus("error");
        }
      },
      onError: () => setStatus("error"),
      onClose: () => { /* surface as idle so the user can re-send */ },
    });

    sockRef.current = sock;
    const isNewCase = lastCaseRef.current && lastCaseRef.current !== caseId;
    sock.init(caseId, stateSnapshot, isNewCase);
    lastCaseRef.current = caseId;

    return () => sock.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, !!stateSnapshot?.result]);

  const send = useCallback((text) => {
    if (!sockRef.current || !text?.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setStatus("streaming");
    sockRef.current.message(text);
  }, []);

  const reset = useCallback(() => {
    setMessages([]);
    setStatus("idle");
    if (sockRef.current && caseId) {
      sockRef.current.init(caseId, stateSnapshot, true);
    }
  }, [caseId, stateSnapshot]);

  return { messages, status, send, reset };
}
