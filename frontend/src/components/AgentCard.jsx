import { useState } from "react";
import { AGENT_LABELS } from "../constants/agents.js";

// Only the FALLBACK badge is rendered. Provider info (Bedrock / Azure) is
// intentionally not chromed onto the card — surfaced via demo narration.
const SOURCE_BADGES = {
  deterministic_fallback: { label: "FALLBACK", cls: "src-fallback" },
};

const PROVIDER_LABELS = {
  llm_bedrock:       "Bedrock",
  llm_azure_foundry: "Azure AI Foundry",
};

// Pretty-print a value for the drill-down view. Lists become bullet counts,
// objects become "{N keys}", primitives render as-is.
function formatEvidenceValue(v) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (Array.isArray(v)) return v.length === 0 ? "[]" : `[${v.length} item${v.length === 1 ? "" : "s"}]`;
  if (typeof v === "object") {
    const keys = Object.keys(v);
    return keys.length === 0 ? "{}" : `{${keys.length} field${keys.length === 1 ? "" : "s"}}`;
  }
  return String(v);
}

export default function AgentCard({ agent, index }) {
  const [expanded, setExpanded] = useState(false);
  const source = agent.evidence?.source;
  const badge  = SOURCE_BADGES[source] ?? null;

  const isFallback   = source === "deterministic_fallback";
  const attempted    = agent.evidence?.attempted_provider;
  const fallbackErr  = agent.evidence?.fallback_reason;
  const attemptedLbl = PROVIDER_LABELS[attempted] ?? attempted ?? "LLM";

  const hasEvidence = agent.evidence && Object.keys(agent.evidence).length > 0;
  const canExpand   = hasEvidence || agent.rule_hits?.length > 0;

  return (
    <div className={`agent-card status-${agent.status} ${expanded ? "agent-card-expanded" : ""}`}>
      <div className="agent-card-top">
        <div className="agent-step">{index}</div>
        {badge && <span className={`source-badge ${badge.cls}`} title={source}>{badge.label}</span>}
      </div>
      <div className="agent-name">{AGENT_LABELS[agent.key]}</div>
      <div className="agent-status">{agent.status}</div>
      {agent.decision && <div className="agent-decision">{agent.decision}</div>}

      {agent.checks?.length > 0 && (
        <ul className="agent-checks">
          {agent.checks.map((c, i) => (
            <li
              key={i}
              className={`agent-check ${c.passed ? "agent-check-passed" : "agent-check-failed"}`}
              title={c.reason || c.label}
            >
              <span className="agent-check-icon" aria-hidden="true">
                {c.passed ? (
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 8 7 12 13 4"/></svg>
                ) : (
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg>
                )}
              </span>
              <span className="agent-check-label">{c.label}</span>
            </li>
          ))}
        </ul>
      )}

      {agent.checks?.length === 0 && agent.rule_hits?.length > 0 && (
        <div className="agent-rules">
          {agent.rule_hits.map((h, i) => (
            <span key={i} className="rule-chip rule-chip-sm" title={h.reason}>{h.rule_id}</span>
          ))}
        </div>
      )}

      {agent.checks?.length === 0 && agent.rule_hits?.length === 0 && agent.reasons?.length > 0 && (
        <ul className="agent-reasons">
          {agent.reasons.slice(0, 4).map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}

      {isFallback && fallbackErr && (
        <div className="fallback-reason" title={fallbackErr}>
          ⚠ {attemptedLbl} error — using deterministic fallback: {fallbackErr}
        </div>
      )}

      {canExpand && (
        <button
          className="agent-expand-toggle"
          onClick={(e) => { e.stopPropagation(); setExpanded((x) => !x); }}
        >
          {expanded ? "Hide details ▴" : "Show data ▾"}
        </button>
      )}

      {expanded && (
        <div className="agent-drilldown">
          {agent.rule_hits?.length > 0 && (
            <div className="agent-drilldown-section">
              <h5>Rules fired</h5>
              <ul className="agent-drilldown-rules">
                {agent.rule_hits.map((h, i) => (
                  <li key={i}>
                    <span className="rule-chip rule-chip-sm">{h.rule_id}</span>
                    <span className="rule-reason">{h.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {hasEvidence && (
            <div className="agent-drilldown-section">
              <h5>Evidence captured</h5>
              <dl className="agent-drilldown-grid">
                {Object.entries(agent.evidence).map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt>{k.replace(/_/g, " ")}</dt>
                    <dd>{formatEvidenceValue(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
