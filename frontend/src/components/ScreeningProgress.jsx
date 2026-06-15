import { AGENT_ORDER, AGENT_LABELS } from "../constants/agents.js";

/**
 * Minimal stepper showing screening progress as dots.
 * Shows which agents have completed without overwhelming detail.
 */
export default function ScreeningProgress({ agents, status }) {
  const completedCount = agents.filter(a => a.status === "done").length;
  const totalCount = AGENT_ORDER.length;
  const isRunning = status === "running";
  const isComplete = completedCount === totalCount && !isRunning;

  return (
    <div className="screening-progress">
      <div className="progress-dots">
        {agents.map((agent, idx) => {
          const isDone = agent.status === "done";
          const isActive = agent.status === "running";
          return (
            <div key={agent.key} className="progress-step">
              <div 
                className={`progress-dot ${isDone ? "dot-done" : ""} ${isActive ? "dot-active" : ""}`}
                title={AGENT_LABELS[agent.key]}
              >
                {isDone && <span className="dot-check">✓</span>}
                {isActive && <span className="dot-pulse" />}
              </div>
              {idx < agents.length - 1 && (
                <div className={`progress-line ${isDone ? "line-done" : ""}`} />
              )}
            </div>
          );
        })}
      </div>
      <div className="progress-label">
        {isRunning && `Analyzing... Step ${completedCount + 1} of ${totalCount}`}
        {isComplete && "Analysis complete"}
        {status === "idle" && "Ready to screen"}
        {status === "error" && "Error occurred"}
      </div>
    </div>
  );
}
