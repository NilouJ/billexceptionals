import { useState } from "react";
import { submitFeedback } from "../api/rest.js";

/**
 * ActionPanel - The primary action-focused view after screening completes.
 * Combines recommendation, next steps, and human review into one cohesive flow.
 * Human review is presented as a required step, not an afterthought.
 */

const RECOMMENDATION_MESSAGES = {
  WORKABLE: {
    title: "Ready for Processing",
    description: "This case is ready to be processed by the billing team.",
    tone: "success"
  },
  RETURN_TO_ONSHORE_EXCLUDED: {
    title: "Return to Onshore",
    description: "This case requires onshore team review due to exclusion criteria.",
    tone: "warning"
  },
  RETURN_TO_ONSHORE_BLOCKED: {
    title: "Blocked - Customer Care Required",
    description: "This case requires customer care team intervention.",
    tone: "warning"
  },
  RETURN_TO_ONSHORE_UNWORKABLE: {
    title: "Requires Specialist Review",
    description: "This case needs metering or tariff specialist review.",
    tone: "warning"
  },
  RETURN_TO_ONSHORE_NEEDS_SOP: {
    title: "SOP Guidance Needed",
    description: "No applicable SOP found. Escalation required.",
    tone: "warning"
  },
};

export default function ActionPanel({ caseId, result, onComplete }) {
  const [reviewState, setReviewState] = useState("pending"); // pending | agreed | disagreed
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [expandedSections, setExpandedSections] = useState({});

  if (!result) return null;

  const {
    recommendation,
    summary,
    reason_codes = [],
    case_pack,
  } = result;

  const recInfo = RECOMMENDATION_MESSAGES[recommendation] || RECOMMENDATION_MESSAGES.WORKABLE;
  const recommended_actions = case_pack?.recommended_actions || [];
  const scenario = case_pack?.scenario;
  const scenario_title = case_pack?.scenario_title;
  const sop_reference = case_pack?.sop_reference;

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitFeedback({ 
        case_id: caseId, 
        agree: reviewState === "agreed", 
        notes, 
        system_result: result 
      });
      setSubmitted(true);
      onComplete?.();
    } catch (e) {
      console.error("Failed to submit feedback:", e);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="action-panel action-panel-submitted">
        <div className="submitted-message">
          <div className="submitted-icon">✓</div>
          <h3>Review Submitted</h3>
          <p>Your feedback has been recorded. Select another case to continue.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="action-panel">
      {/* Recommendation Header */}
      <div className={`action-header tone-${recInfo.tone}`}>
        <div className="action-badge">{recommendation}</div>
        <h2 className="action-title">{recInfo.title}</h2>
        <p className="action-description">{summary || recInfo.description}</p>
      </div>

      {/* Scenario & SOP (if available) */}
      {(scenario || sop_reference) && (
        <div className="action-context">
          {scenario && (
            <div className="context-row">
              <span className="context-label">Scenario</span>
              <span className="context-value">
                <span className="scenario-badge">{scenario}</span>
                {scenario_title}
              </span>
            </div>
          )}
          {sop_reference?.id && (
            <div className="context-row">
              <span className="context-label">SOP</span>
              <span className="context-value">{sop_reference.id} — {sop_reference.title}</span>
            </div>
          )}
        </div>
      )}

      {/* What You Need To Do - Primary Focus */}
      {recommended_actions.length > 0 && (
        <div className="action-tasks">
          <h3>
            <span className="tasks-icon">📋</span>
            What You Need To Do
          </h3>
          <ul className="task-list">
            {recommended_actions.map((action, i) => (
              <li key={i} className="task-item">
                <span className="task-number">{i + 1}</span>
                <span className="task-text">{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Expandable Details */}
      <div className="action-details">
        {reason_codes.length > 0 && (
          <button 
            className={`detail-toggle ${expandedSections.reasons ? "expanded" : ""}`}
            onClick={() => toggleSection("reasons")}
          >
            <span>Why this recommendation?</span>
            <span className="toggle-icon">{expandedSections.reasons ? "▲" : "▼"}</span>
          </button>
        )}
        {expandedSections.reasons && (
          <ul className="detail-list">
            {reason_codes.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}

        {case_pack?.account_summary && (
          <button 
            className={`detail-toggle ${expandedSections.account ? "expanded" : ""}`}
            onClick={() => toggleSection("account")}
          >
            <span>Account details</span>
            <span className="toggle-icon">{expandedSections.account ? "▲" : "▼"}</span>
          </button>
        )}
        {expandedSections.account && (
          <dl className="detail-grid">
            {Object.entries(case_pack.account_summary)
              .filter(([_, v]) => v !== null && v !== undefined && v !== "")
              .map(([k, v]) => (
                <div key={k} className="detail-row">
                  <dt>{k.replace(/_/g, " ")}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
          </dl>
        )}
      </div>

      {/* Human Review - Required Step */}
      <div className="human-review">
        <div className="review-header">
          <h3>
            <span className="review-icon">👤</span>
            Your Review
            <span className="required-badge">Required</span>
          </h3>
          <p className="review-subtitle">Confirm or challenge the AI recommendation</p>
        </div>

        <div className="review-options">
          <button 
            className={`review-option ${reviewState === "agreed" ? "selected" : ""}`}
            onClick={() => setReviewState("agreed")}
          >
            <span className="option-icon">✓</span>
            <span className="option-label">Agree</span>
            <span className="option-desc">Proceed with recommendation</span>
          </button>
          <button 
            className={`review-option ${reviewState === "disagreed" ? "selected" : ""}`}
            onClick={() => setReviewState("disagreed")}
          >
            <span className="option-icon">✗</span>
            <span className="option-label">Disagree</span>
            <span className="option-desc">Flag for re-triage</span>
          </button>
        </div>

        <textarea 
          className="review-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={reviewState === "disagreed" ? "Please explain why you disagree..." : "Optional notes..."}
          rows={3}
        />

        <button 
          className="submit-review"
          disabled={reviewState === "pending" || submitting}
          onClick={handleSubmit}
        >
          {submitting ? "Submitting..." : "Submit Review & Continue"}
        </button>
      </div>
    </div>
  );
}
