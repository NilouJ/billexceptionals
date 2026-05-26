export default function TraceLog({ trace }) {
  if (!trace.length) return null;

  return (
    <section className="trace-log">
      <h3>Live Trace</h3>
      <ol>
        {trace.map((t, i) => (
          <li key={i} className="trace-item">
            <div className="trace-header">
              <strong>{t.agent}</strong> → <em>{t.decision}</em>
            </div>
            {t.rule_hits?.length > 0 ? (
              <ul className="rule-list">
                {t.rule_hits.map((h, j) => (
                  <li key={j}>
                    <span className="rule-chip">{h.rule_id}</span>
                    {h.reason}
                  </li>
                ))}
              </ul>
            ) : t.reasons?.length > 0 && (
              <ul className="rule-list">
                {t.reasons.map((r, j) => <li key={j}><span className="rule-muted">no rule</span>{r}</li>)}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}