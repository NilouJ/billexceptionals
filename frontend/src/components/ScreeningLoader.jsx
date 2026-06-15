/**
 * ScreeningLoader - Shows while agents are processing the case.
 * Clean, minimal loading state that indicates work is happening
 * without overwhelming the user with step-by-step details.
 */
export default function ScreeningLoader({ caseId }) {
  return (
    <div className="screening-loader">
      <div className="loader-content">
        <div className="loader-spinner">
          <div className="spinner-ring" />
          <div className="spinner-icon">🤖</div>
        </div>
        <h3 className="loader-title">Analyzing Case</h3>
        <p className="loader-subtitle">
          AI agents are screening this exception...
        </p>
        <div className="loader-case">
          Case {caseId}
        </div>
      </div>
    </div>
  );
}
