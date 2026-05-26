export default function FinalResult({ result }) {
  if (!result) return null;

  const {
    recommendation,
    summary,
    rationale,
    next_action,
    reason_codes = [],
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

      <details className="final-raw">
        <summary>Raw result JSON</summary>
        <pre>{JSON.stringify(result, null, 2)}</pre>
      </details>
    </section>
  );
}