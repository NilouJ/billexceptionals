// Action chips after the recommendation — UI-only affordance, no backend action.
// Sized to the outcome so the analyst always knows what to do next.
const NEXT_ACTIONS = {
  WORKABLE: [
    { label: "Send to billing queue", primary: true },
    { label: "Override decision" },
    { label: "Ask the assistant", target: "chat" },
  ],
  RETURN_TO_ONSHORE_EXCLUDED: [
    { label: "Send to onshore queue", primary: true },
    { label: "Override decision" },
    { label: "Ask the assistant", target: "chat" },
  ],
  RETURN_TO_ONSHORE_BLOCKED: [
    { label: "Send to onshore (customer care)", primary: true },
    { label: "Override decision" },
    { label: "Ask the assistant", target: "chat" },
  ],
  RETURN_TO_ONSHORE_UNWORKABLE: [
    { label: "Send to onshore (metering/tariff)", primary: true },
    { label: "Override decision" },
    { label: "Ask the assistant", target: "chat" },
  ],
  RETURN_TO_ONSHORE_NEEDS_SOP: [
    { label: "Escalate for SOP guidance", primary: true },
    { label: "Override decision" },
    { label: "Ask the assistant", target: "chat" },
  ],
};


function NextActions({ recommendation }) {
  const actions = NEXT_ACTIONS[recommendation] || NEXT_ACTIONS.WORKABLE;
  const onClick = (a) => {
    if (a.target === "chat") {
      // Focus the chat input — best-effort, no harm if not present
      document.querySelector(".chat-input")?.focus();
      return;
    }
    // Other actions are demo affordances — show a console hint for now.
    console.info(`[demo] action: ${a.label}`);
  };
  return (
    <div className="next-actions">
      {actions.map((a, i) => (
        <button
          key={i}
          className={`next-action ${a.primary ? "next-action-primary" : ""}`}
          onClick={() => onClick(a)}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}


function CasePackBlock({ case_pack }) {
  if (!case_pack) return null;
  const {
    scenario,
    scenario_title,
    account_summary = {},
    sop_reference = {},
    recommended_actions = [],
  } = case_pack;

  return (
    <div className="case-pack-block">
      <div className="case-pack-header">
        <h4>Scenario</h4>
        {scenario && <span className="case-pack-scenario">{scenario}</span>}
        <span>{scenario_title}</span>
      </div>

      {sop_reference?.id && (
        <div className="case-pack-sop">
          <div className="case-pack-sop-id">{sop_reference.id}</div>
          <div className="case-pack-sop-title">{sop_reference.title}</div>
          {sop_reference.key_steps?.length > 0 && (
            <ol className="case-pack-sop-steps">
              {sop_reference.key_steps.map((s, i) => <li key={i}>{s}</li>)}
            </ol>
          )}
        </div>
      )}

      {recommended_actions.length > 0 && (
        <div className="final-block">
          <h4>Recommended actions</h4>
          <ul className="case-pack-actions">
            {recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}

      <div className="final-block">
        <h4>Account summary</h4>
        <dl className="case-pack-grid">
          {Object.entries(account_summary)
            .filter(([_, v]) => v !== null && v !== undefined && v !== "")
            .map(([k, v]) => (
              <div key={k} style={{ display: "contents" }}>
                <dt>{k.replace(/_/g, " ")}</dt>
                <dd>{String(v)}</dd>
              </div>
            ))}
        </dl>
      </div>
    </div>
  );
}


export default function FinalResult({ result }) {
  if (!result) return null;

  const {
    recommendation,
    summary,
    rationale,
    next_action,
    reason_codes = [],
    case_pack,
  } = result;

  return (
    <section className="final-result">
      <h3>Final Result</h3>

      <div className="final-recommendation">{recommendation}</div>

      {summary && <p className="final-summary">{summary}</p>}

      {rationale && (
        <div className="final-block">
          <h4>Rationale</h4>
          <p>{rationale}</p>
        </div>
      )}

      {next_action && (
        <div className="final-block">
          <h4>Next action</h4>
          <p>{next_action}</p>
        </div>
      )}

      {reason_codes.length > 0 && (
        <div className="final-block">
          <h4>Reason codes</h4>
          <ul className="final-reasons">
            {reason_codes.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {case_pack && <CasePackBlock case_pack={case_pack} />}

      <NextActions recommendation={recommendation} />

      <details className="final-raw">
        <summary>Raw result JSON</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </section>
  );
}
