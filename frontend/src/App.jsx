import { useEffect, useMemo, useRef, useState } from "react";
import CaseList from "./components/CaseList.jsx";
import CaseDetails from "./components/CaseDetails.jsx";
import ScreeningLoader from "./components/ScreeningLoader.jsx";
import ScreeningStages from "./components/ScreeningStages.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import BatchDashboard from "./components/BatchDashboard.jsx";
import useScreening from "./hooks/useScreening.js";
import { fetchCases } from "./api/rest.js";
import { openBatchSocket } from "./api/websocket.js";
import "./styles/App.css";

const PAGE_SIZE = 20;

export default function App() {
  const [selectedCase, setSelectedCase] = useState(null);
  const [cases, setCases] = useState([]);
  const [casesTotal, setCasesTotal] = useState(0);
  const [casesPages, setCasesPages] = useState(1);
  const [casesError, setCasesError] = useState(null);
  const [runs, setRuns] = useState({}); // exception_id -> recommendation
  const [caseResults, setCaseResults] = useState({}); // exception_id -> { result, trace }
  const [batchStatus, setBatchStatus] = useState("idle"); // idle | running | done | error
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 });
  const batchSockRef = useRef(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { agents, trace, result, status, run, reset, applyCachedRun } = useScreening();

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

  // Record the recommendation for each case as live runs complete.
  useEffect(() => {
    if (!result || !selectedCase) return;
    const id = selectedCase.exception_id;
    const rec = result.recommendation;
    if (!id || !rec) return;
    setRuns((prev) => (prev[id] === rec ? prev : { ...prev, [id]: rec }));
    setCaseResults((prev) => ({ ...prev, [id]: { result, trace } }));
  }, [result, selectedCase, trace]);

  const onRunSelected = () => {
    if (!selectedCase) return;
    reset();
    run({ ...selectedCase, case_id: selectedCase.case_id ?? selectedCase.exception_id });
  };

  const onRunBatch = () => {
    if (batchStatus === "running") return;
    reset();
    setSelectedCase(null);
    setBatchStatus("running");
    setBatchProgress({ done: 0, total: 0 });

    const sock = openBatchSocket({
      onEvent: (evt) => {
        if (evt.type === "batch_start") {
          setBatchProgress({ done: 0, total: evt.total });
        } else if (evt.type === "case_done") {
          const rec = evt.result?.recommendation;
          if (evt.case_id && rec) {
            setRuns((prev) => ({ ...prev, [evt.case_id]: rec }));
            setCaseResults((prev) => ({
              ...prev,
              [evt.case_id]: { result: evt.result, trace: evt.trace || [] },
            }));
          }
          setBatchProgress((prev) => ({ ...prev, done: prev.done + 1 }));
        } else if (evt.type === "case_failed") {
          setBatchProgress((prev) => ({ ...prev, done: prev.done + 1 }));
        } else if (evt.type === "batch_done") {
          setBatchStatus("done");
          batchSockRef.current?.close?.();
          batchSockRef.current = null;
        } else if (evt.type === "error") {
          setBatchStatus("error");
        }
      },
      onError: () => setBatchStatus("error"),
      onClose: () => {
        setBatchStatus((s) => (s === "running" ? "done" : s));
      },
    });
    batchSockRef.current = sock;
  };

  const handleSelectCase = (c) => {
    const changed = (c?.exception_id ?? null) !== (selectedCase?.exception_id ?? null);
    if (changed) {
      const cached = c?.exception_id ? caseResults[c.exception_id] : null;
      if (cached) {
        applyCachedRun(cached);
      } else {
        reset();
      }
    }
    setSelectedCase(c);
  };

  const resetDemo = () => {
    batchSockRef.current?.close?.();
    batchSockRef.current = null;
    setRuns({});
    setCaseResults({});
    setBatchStatus("idle");
    setBatchProgress({ done: 0, total: 0 });
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
          batchStatus={batchStatus}
          batchProgress={batchProgress}
        />

        <header className="main-header">
          <div className="page-title">
            <h1>Bill Exceptions Assistant</h1>
            <p className="page-subtitle">UC-1 Triage · multi-agent screening funnel</p>
          </div>
          <div className="header-actions">
            <button
              className="btn-secondary"
              onClick={onRunBatch}
              disabled={batchStatus === "running" || status === "running"}
              title="Run screening on every case at once"
            >
              {batchStatus === "running" ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  Running batch… {batchProgress.done}/{batchProgress.total || "…"}
                </>
              ) : (
                "Run Batch"
              )}
            </button>
            <button
              className="btn-primary"
              onClick={onRunSelected}
              disabled={!selectedCase || status === "running" || batchStatus === "running"}
            >
              {status === "running" ? "Running…" : "Run Selected"}
            </button>
          </div>
        </header>

        <CaseDetails caseData={selectedCase} />

        {status === "running" && agents.every((a) => a.status === "pending") && (
          <ScreeningLoader caseId={selectedCase?.case_id ?? selectedCase?.exception_id} />
        )}

        {(status !== "idle" && !agents.every((a) => a.status === "pending")) && (
          <ScreeningStages
            agents={agents}
            trace={trace}
            result={result}
            status={status}
            caseId={selectedCase?.case_id ?? selectedCase?.exception_id}
          />
        )}
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
