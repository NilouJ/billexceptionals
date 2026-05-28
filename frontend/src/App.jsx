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

const PAGE_SIZE = 20;

export default function App() {
  const [selectedCase, setSelectedCase] = useState(null);
  const [cases, setCases] = useState([]);
  const [casesTotal, setCasesTotal] = useState(0);
  const [casesPages, setCasesPages] = useState(1);
  const [casesError, setCasesError] = useState(null);
  const [runs, setRuns] = useState({}); // exception_id -> recommendation
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { agents, trace, result, status, run, reset } = useScreening();

  // Debounce search input by 300 ms
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset to page 1 whenever the search term changes
  useEffect(() => { setPage(1); }, [debouncedSearch]);

  // Fetch the current page whenever page or debouncedSearch changes
  useEffect(() => {
    setCasesError(null);
    fetchCases({ page, pageSize: PAGE_SIZE, search: debouncedSearch })
      .then(({ items, total, pages }) => {
        setCases(items);
        setCasesTotal(total);
        setCasesPages(pages);
      })
      .catch((e) => setCasesError(e.message));
  }, [page, debouncedSearch]);

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
    setPage(1);
    setSearch("");
    setDebouncedSearch("");
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
  const [chatOpen, setChatOpen] = useState(false);

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
          total={casesTotal}
          page={page}
          pages={casesPages}
          onPageChange={setPage}
          search={search}
          onSearch={setSearch}
        />
      </aside>

      <main className="main">
        <BatchDashboard
          batchSize={casesTotal}
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

      <ChatPanel
        caseId={chatCaseId}
        stateSnapshot={chatStateSnapshot}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />

      {/* FAB chat bubble */}
      <button
        className={`chat-fab${chatOpen ? " chat-fab-active" : ""}`}
        onClick={() => setChatOpen((o) => !o)}
        aria-label="Toggle chat assistant"
      >
        {chatOpen ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        )}
      </button>
    </div>
  );
}
