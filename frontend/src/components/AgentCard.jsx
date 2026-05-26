import { AGENT_LABELS } from "../constants/agents.js";

// Map evidence.source from the backend to the badge shown on the agent card.
// Provider tags are emitted by backend/model_provider.py:provider_source_tag().
const SOURCE_BADGES = {
  llm_bedrock:           { label: "Claude · Bedrock", cls: "src-llm src-bedrock" },
  llm_azure_foundry:     { label: "Claude · Azure",   cls: "src-llm src-azure" },
  deterministic_fallback:{ label: "FALLBACK",         cls: "src-fallback" },
};

const PROVIDER_LABELS = {
  llm_bedrock:       "Bedrock",
  llm_azure_foundry: "Azure AI Foundry",
};

export default function AgentCard({ agent, index }) {
  const source = agent.evidence?.source;
  const badge  = SOURCE_BADGES[source] ?? null;

  const isFallback   = source === "deterministic_fallback";
  const attempted    = agent.evidence?.attempted_provider;
  const fallbackErr  = agent.evidence?.fallback_reason;
  const attemptedLbl = PROVIDER_LABELS[attempted] ?? attempted ?? "LLM";

  return (
    <div className={`agent-card status-${agent.status}`}>
      <div className="agent-card-top">
        <div className="agent-step">{index}</div>
        {badge && <span className={`source-badge ${badge.cls}`} title={source}>{badge.label}</span>}
      </div>
      <div className="agent-name">{AGENT_LABELS[agent.key]}</div>
      <div className="agent-status">{agent.status}</div>
      {agent.decision && <div className="agent-decision">{agent.decision}</div>}

      {agent.rule_hits?.length > 0 && (
        <div className="agent-rules">
          {agent.rule_hits.map((h, i) => (
            <span key={i} className="rule-chip rule-chip-sm" title={h.reason}>{h.rule_id}</span>
          ))}
        </div>
      )}

      {agent.rule_hits?.length === 0 && agent.reasons?.length > 0 && (
        <ul className="agent-reasons">
          {agent.reasons.slice(0, 4).map((r, i) => <li key={i}>{r}</li>)}
        </ul>
      )}

      {isFallback && fallbackErr && (
        <div className="fallback-reason" title={fallbackErr}>
          ⚠ {attemptedLbl} error — using deterministic fallback: {fallbackErr}
        </div>
      )}
    </div>
  );
}
