export default function CaseDetails({ caseData }) {
  if (!caseData) return <section className="case-details empty">Select a case to begin.</section>;

  return (
    <section className="case-details">
      <h2>Case {caseData.exception_id}</h2>
      <dl>
        <dt>Account</dt><dd>{caseData.account_number}</dd>
        <dt>ESIID</dt><dd>{caseData.esiid}</dd>
        <dt>Exception</dt><dd>{caseData.exception_type}</dd>
      </dl>
    </section>
  );
}