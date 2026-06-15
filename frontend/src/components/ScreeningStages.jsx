import { useState, useEffect } from "react";
import AgentCard from "./AgentCard.jsx";
import { submitFeedback } from "../api/rest.js";

const STAGES = [
  { id: 1, key: "processing",     label: "Processing",     hint: "Agent analysis"       },
  { id: 2, key: "recommendation", label: "Recommendation", hint: "Why this decision"    },
  { id: 3, key: "review",         label: "Your Review",    hint: "Required",  required: true },
];

const RECOMMENDATION_CONFIG = {
  WORKABLE:                        { tone: "success", title: "Ready for Processing",        desc: "This case is ready to be processed by the billing team."                          },
  RETURN_TO_ONSHORE_EXCLUDED:      { tone: "warning", title: "Return to Onshore",           desc: "This case requires onshore team review due to exclusion criteria."                },
  RETURN_TO_ONSHORE_BLOCKED:       { tone: "warning", title: "Blocked — Customer Care",     desc: "This case requires customer care team intervention before processing."            },
  RETURN_TO_ONSHORE_UNWORKABLE:    { tone: "warning", title: "Requires Specialist Review",  desc: "This case needs metering or tariff specialist review."                           },
  RETURN_TO_ONSHORE_NEEDS_SOP:     { tone: "warning", title: "SOP Guidance Needed",         desc: "No applicable SOP found. Escalation required."                                  },
};

/* ─── Stage Nav ──────────────────────────────────────────────────────────── */
function StageNav({ activeStage, onSelect, isAccessible, submitted }) {
  return (
    <div className="stage-nav">
      {STAGES.map((stage, idx) => {
        const accessible = isAccessible(stage.id);
        const active     = activeStage === stage.id;
        const complete   = activeStage > stage.id || (stage.id === 3 && submitted);
        return (
          <div key={stage.id} className="stage-nav-item">
            <button
              className={`stage-btn ${active ? "stage-btn-active" : ""} ${complete ? "stage-btn-complete" : ""} ${!accessible ? "stage-btn-locked" : ""}`}
              onClick={() => accessible && onSelect(stage.id)}
              disabled={!accessible}
            >
              <span className="stage-num">
                {complete ? "✓" : stage.id}
              </span>
              <span className="stage-info">
                <span className="stage-label">{stage.label}</span>
                <span className={`stage-hint ${stage.required ? "stage-hint-required" : ""}`}>
                  {stage.hint}
                </span>
              </span>
            </button>
            {idx < STAGES.length - 1 && (
              <div className={`stage-connector ${accessible ? "connector-active" : ""}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Stage 1: Processing ─────────────────────────────────────────────────── */
function StageProcessing({ agents, trace, status, onAdvance }) {
  const isRunning  = status === "running";
  const isComplete = status === "done" || (status !== "running" && agents.some(a => a.status === "done"));

  return (
    <div className="stage-body">
      {isRunning && (
        <div className="stage-running-banner">
          <span className="running-dot" />
          AI agents are analyzing this case…
        </div>
      )}

      {/* Agent cards grid */}
      <div className="pipeline">
        {agents.map((a, i) => (
          <AgentCard key={a.key} agent={a} index={i + 1} />
        ))}
      </div>

      {/* Live trace */}
      {trace.length > 0 && (
        <div className="stage-trace">
          <h4 className="stage-section-title">Live Trace</h4>
          <ol className="trace-list">
            {trace.map((t, i) => (
              <li key={i} className="trace-item">
                <div className="trace-header">
                  <strong>{t.agent}</strong>
                  <span className="trace-arrow">→</span>
                  <em>{t.decision}</em>
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
                    {t.reasons.map((r, j) => (
                      <li key={j}><span className="rule-muted">no rule</span>{r}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {isComplete && (
        <div className="stage-advance-row">
          <button className="stage-advance-btn" onClick={onAdvance}>
            View Recommendation →
          </button>
        </div>
      )}
    </div>
  );
}

/* ─── Stage 2: Recommendation ────────────────────────────────────────────── */
function StageRecommendation({ result, onAdvance }) {
  const [expandedSections, setExpandedSections] = useState({});

  const toggle = (key) => setExpandedSections(p => ({ ...p, [key]: !p[key] }));

  const {
    recommendation,
    summary,
    reason_codes = [],
    rationale,
    next_action,
    case_pack,
  } = result;

  const cfg               = RECOMMENDATION_CONFIG[recommendation] || RECOMMENDATION_CONFIG.WORKABLE;
  const { scenario, scenario_title, sop_reference, recommended_actions = [], account_summary = {} } = case_pack || {};

  return (
    <div className="stage-body">
      {/* Recommendation hero */}
      <div className={`rec-hero tone-${cfg.tone}`}>
        <div className="rec-badge">{recommendation}</div>
        <h2 className="rec-title">{cfg.title}</h2>
        <p className="rec-desc">{summary || cfg.desc}</p>
      </div>

      {/* Scenario + SOP context */}
      {(scenario || sop_reference?.id) && (
        <div className="rec-context">
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

      {/* What you need to do */}
      {recommended_actions.length > 0 && (
        <div className="rec-tasks">
          <h4 className="stage-section-title">What You Need To Do</h4>
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

      {/* Expandable: Why this recommendation */}
      {(reason_codes.length > 0 || rationale) && (
        <div className="rec-expandable">
          <button className="detail-toggle" onClick={() => toggle("why")}>
            <span>Why this recommendation?</span>
            <span className="toggle-icon">{expandedSections.why ? "▲" : "▼"}</span>
          </button>
          {expandedSections.why && (
            <div className="detail-content">
              {reason_codes.length > 0 && (
                <ul className="detail-list">
                  {reason_codes.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
              {rationale && <p className="detail-rationale">{rationale}</p>}
              {next_action && <p className="detail-next-action"><strong>Next action:</strong> {next_action}</p>}
            </div>
          )}
        </div>
      )}

      {/* Expandable: SOP steps */}
      {sop_reference?.key_steps?.length > 0 && (
        <div className="rec-expandable">
          <button className="detail-toggle" onClick={() => toggle("sop")}>
            <span>SOP Steps — {sop_reference.id}</span>
            <span className="toggle-icon">{expandedSections.sop ? "▲" : "▼"}</span>
          </button>
          {expandedSections.sop && (
            <div className="detail-content">
              <ol className="sop-steps-list">
                {sop_reference.key_steps.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            </div>
          )}
        </div>
      )}

      {/* Expandable: Account summary */}
      {Object.keys(account_summary).length > 0 && (
        <div className="rec-expandable">
          <button className="detail-toggle" onClick={() => toggle("account")}>
            <span>Account Details</span>
            <span className="toggle-icon">{expandedSections.account ? "▲" : "▼"}</span>
          </button>
          {expandedSections.account && (
            <div className="detail-content">
              <dl className="detail-grid">
                {Object.entries(account_summary)
                  .filter(([_, v]) => v !== null && v !== undefined && v !== "")
                  .map(([k, v]) => (
                    <div key={k} className="detail-row">
                      <dt>{k.replace(/_/g, " ")}</dt>
                      <dd>{String(v)}</dd>
                    </div>
                  ))}
              </dl>
            </div>
          )}
        </div>
      )}

      <div className="stage-advance-row">
        <button className="stage-advance-btn" onClick={onAdvance}>
          Proceed to Your Review →
        </button>
      </div>
    </div>
  );
}

/* ─── Stage 3: Human Review ──────────────────────────────────────────────── */
function StageReview({ caseId, result, onSubmitted }) {
  const [agree,      setAgree]      = useState(null);   // true | false | null
  const [notes,      setNotes]      = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted,  setSubmitted]  = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitFeedback({ case_id: caseId, agree, notes, system_result: result });
      setSubmitted(true);
      onSubmitted?.();
    } catch (e) {
      console.error("Failed to submit feedback:", e);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="stage-body stage-submitted">
        <div className="submitted-icon">✓</div>
        <h3>Review Submitted</h3>
        <p>Your feedback has been recorded. Select another case to continue.</p>
      </div>
    );
  }

  return (
    <div className="stage-body">
      <div className="review-intro">
        <h3 className="review-intro-title">Your Assessment</h3>
        <p className="review-intro-desc">
          Do you agree with the AI recommendation? Your input improves future screening accuracy.
        </p>
      </div>

      <div className="review-options">
        <button
          className={`review-option ${agree === true ? "selected agree" : ""}`}
          onClick={() => setAgree(true)}
        >
          <span className="option-icon">✓</span>
          <span className="option-label">Agree</span>
          <span className="option-desc">Proceed with recommendation</span>
        </button>
        <button
          className={`review-option ${agree === false ? "selected disagree" : ""}`}
          onClick={() => setAgree(false)}
        >
          <span className="option-icon">✗</span>
          <span className="option-label">Disagree</span>
          <span className="option-desc">Flag for re-triage</span>
        </button>
      </div>

      <div className="review-notes-wrap">
        <label className="review-notes-label">
          {agree === false ? "Reason for disagreement *" : "Notes (optional)"}
        </label>
        <textarea
          className="review-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={agree === false ? "Explain why you disagree…" : "Any additional context…"}
          rows={4}
        />
      </div>

      <button
        className="submit-review"
        disabled={agree === null || (agree === false && !notes.trim()) || submitting}
        onClick={handleSubmit}
      >
        {submitting ? "Submitting…" : "Submit Review"}
      </button>

      {agree === false && !notes.trim() && (
        <p className="review-hint">Please add a reason when disagreeing.</p>
      )}
    </div>
  );
}

/* ─── Main Orchestrator ──────────────────────────────────────────────────── */
export default function ScreeningStages({ agents, trace, result, status, caseId }) {
  const [activeStage, setActiveStage] = useState(1);
  const [submitted,   setSubmitted]   = useState(false);

  // Auto-advance to stage 2 when result arrives from stage 1
  useEffect(() => {
    if (result && activeStage === 1) {
      setActiveStage(2);
    }
  }, [result]);

  // Reset when caseId changes
  useEffect(() => {
    setActiveStage(1);
    setSubmitted(false);
  }, [caseId]);

  const isAccessible = (id) => {
    if (id === 1) return true;
    if (id === 2) return !!result;
    if (id === 3) return !!result;
    return false;
  };

  return (
    <div className="screening-stages">
      <StageNav
        activeStage={activeStage}
        onSelect={setActiveStage}
        isAccessible={isAccessible}
        submitted={submitted}
      />

      <div className="stage-content">
        {activeStage === 1 && (
          <StageProcessing
            agents={agents}
            trace={trace}
            status={status}
            onAdvance={() => setActiveStage(2)}
          />
        )}
        {activeStage === 2 && result && (
          <StageRecommendation
            result={result}
            onAdvance={() => setActiveStage(3)}
          />
        )}
        {activeStage === 3 && result && (
          <StageReview
            caseId={caseId}
            result={result}
            onSubmitted={() => setSubmitted(true)}
          />
        )}
      </div>
    </div>
  );
}
