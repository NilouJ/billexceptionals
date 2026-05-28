import { useCallback, useRef, useState } from "react";
import { openScreeningSocket } from "../api/websocket.js";
import { AGENT_ORDER, AGENT_STATUS } from "../constants/agents.js";

const initialAgents = () =>
  AGENT_ORDER.map((key) => ({ key, status: AGENT_STATUS.PENDING, decision: null, reasons: [], rule_hits: [], evidence: {}, checks: [] }));

export default function useScreening() {
  const [agents, setAgents] = useState(initialAgents);
  const [trace, setTrace] = useState([]);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const sockRef = useRef(null);

  const reset = useCallback(() => {
    sockRef.current?.close?.();
    sockRef.current = null;
    setAgents(initialAgents());
    setTrace([]);
    setResult(null);
    setStatus("idle");
  }, []);

  // Hydrate the screening view from a cached batch result, no WebSocket.
  // Used when the user selects a case that was already processed in batch.
  const applyCachedRun = useCallback(({ result: cachedResult, trace: cachedTrace = [] } = {}) => {
    sockRef.current?.close?.();
    sockRef.current = null;
    const byKey = Object.fromEntries(cachedTrace.map((t) => [t.agent_key, t]));
    setAgents(AGENT_ORDER.map((key) => {
      const t = byKey[key];
      return t
        ? { key, status: AGENT_STATUS.DONE, decision: t.decision, reasons: t.reasons || [], rule_hits: t.rule_hits || [], evidence: t.evidence || {}, checks: t.checks || [] }
        : { key, status: AGENT_STATUS.PENDING, decision: null, reasons: [], rule_hits: [], evidence: {}, checks: [] };
    }));
    setTrace(cachedTrace);
    setResult(cachedResult ?? null);
    setStatus(cachedResult ? "done" : "idle");
  }, []);

  const applyEvent = useCallback((evt) => {
    if (evt.type === "agent_status") {
      setAgents((prev) =>
        prev.map((a) =>
          a.key === evt.agent_key
            ? {
                ...a,
                status: evt.status,
                decision: evt.decision ?? a.decision,
                reasons: evt.reasons ?? a.reasons,
                rule_hits: evt.rule_hits ?? a.rule_hits,
                evidence: evt.evidence ?? a.evidence,
                checks: evt.checks ?? a.checks,
              }
            : a
        )
      );
      if (evt.status === "done") {
        setTrace((prev) => [...prev, {
          agent_key: evt.agent_key,
          agent: evt.agent,
          decision: evt.decision,
          reasons: evt.reasons,
          rule_hits: evt.rule_hits || [],
          evidence: evt.evidence || {},
          checks: evt.checks || [],
        }]);
      }
    } else if (evt.type === "final_result") {
      setResult(evt.result);
      setStatus("done");
    } else if (evt.type === "error") {
      console.error("backend error:", evt.message);
      setStatus("error");
    }
  }, []);

  const run = useCallback((caseData) => {
    setStatus("running");
    const sock = openScreeningSocket({
      onEvent: applyEvent,
      onError: () => setStatus("error"),
    });
    sockRef.current = sock;
    sock.sendCase(caseData);
  }, [applyEvent]);

  return { agents, trace, result, status, run, reset, applyCachedRun };
}