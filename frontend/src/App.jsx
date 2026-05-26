import { useState } from "react";
import CaseList from "./components/CaseList.jsx";
import CaseDetails from "./components/CaseDetails.jsx";
import AgentPipeline from "./components/AgentPipeline.jsx";
import TraceLog from "./components/TraceLog.jsx";
import FinalResult from "./components/FinalResult.jsx";
import FeedbackForm from "./components/FeedbackForm.jsx";
import useScreening from "./hooks/useScreening.js";
import "./styles/App.css";

export default function App() {
  const [selectedCase, setSelectedCase] = useState(null);
  const { agents, trace, result, status, run, reset } = useScreening();

  const onRun = () => {
    if (!selectedCase) return;
    reset();
    run({ ...selectedCase, case_id: selectedCase.case_id ?? selectedCase.exception_id });
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <CaseList onSelect={setSelectedCase} selectedId={selectedCase?.exception_id} />
      </aside>

      <main className="main">
        <header className="main-header">
          <h1>Origin Billing Exception Screening</h1>
          <button className="btn-primary" onClick={onRun} disabled={!selectedCase || status === "running"}>
            {status === "running" ? "Running…" : "Run Screening"}
          </button>
        </header>

        <CaseDetails caseData={selectedCase} />
        <AgentPipeline agents={agents} />
        <TraceLog trace={trace} />
        {result && <FinalResult result={result} />}
        {result && selectedCase && <FeedbackForm caseId={selectedCase.exception_id} result={result} />}
      </main>
    </div>
  );
}