import { useEffect, useMemo, useState } from "react";
import CaseList from "./components/CaseList.jsx";
import CaseDetails from "./components/CaseDetails.jsx";
import AgentPipeline from "./components/AgentPipeline.jsx";
import TraceLog from "./components/TraceLog.jsx";
import FinalResult from "./components/FinalResult.jsx";
import FeedbackForm from "./components/FeedbackForm.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import BatchDashboard from "./components/BatchDashboard.jsx";
import useScreening from "./hooks/useScreening.js";
import { fetchCases } from "./api/rest.js";
import "./styles/App.css";

export default function App() {
  const [selectedCase, setSelectedCase] = useState(null);
  const [cases, setCases] = useState([]);
  const [casesError, setCasesError] = useState(null);
  const [runs, setRuns] = useState({}); // exception_id -> recommendation
  const { agents, trace, result, status, run, reset } = useScreening();

  useEffect(() => {
    fetchCases().then(setCases).catch((e) => setCasesError(e.message));
  }, []);

  // Record the recommendation for each case as runs complete.
  useEffect(() => {
    if (!result || !selectedCase) return;
    const id = selectedCase.exception_id;
    const rec = result.recommendation;
    if (!id || !rec) return;
    setRuns((prev) => (prev[id] === rec ? prev : { ...prev, [id]: rec }));
  }, [result, selectedCase]);

  const onRun = () => {
    if (!selectedCase) return;
    reset();
    run({ ...selectedCase, case_id: selectedCase.case_id ?? selectedCase.exception_id });
  };

  const handleSelectCase = (c) => {
    if ((c?.exception_id ?? null) !== (selectedCase?.exception_id ?? null)) {
      reset();
    }
    setSelectedCase(c);
  };

  const resetDemo = () => {
    setRuns({});
    reset();
    setSelectedCase(null);
  };

  // Snapshot the screening state for the chat panel. Built from what the
  // frontend already has — case + trace + result (which includes case_pack).
  const chatStateSnapshot = useMemo(() => {
    if (!selectedCase || !result) return null;
    return {
      case: { ...selectedCase, case_id: selectedCase.case_id ?? selectedCase.exception_id },
      trace,
      result,
    };
  }, [selectedCase, trace, result]);

  const chatCaseId = selectedCase?.case_id ?? selectedCase?.exception_id ?? null;

  return (
    <div className="app">
      <aside className="sidebar">
        <a href="/" className="brand-link">
          <img src="/origin-logo.png" alt="Origin" className="brand-logo" />
        </a>
        <CaseList
          cases={cases}
          runs={runs}
          error={casesError}
          onSelect={handleSelectCase}
          selectedId={selectedCase?.exception_id}
        />
      </aside>

      <main className="main">
        <BatchDashboard
          batchSize={cases.length}
          runs={runs}
          onReset={resetDemo}
        />

        <header className="main-header">
          <div className="page-title">
            <h1>Bill Exceptions Assistant</h1>
            <p className="page-subtitle">UC-1 Triage · multi-agent screening funnel</p>
          </div>
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

      <ChatPanel caseId={chatCaseId} stateSnapshot={chatStateSnapshot} />
    </div>
  );
}
