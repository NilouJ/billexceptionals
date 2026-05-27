import { useMemo, useState } from "react";

const STATUS_FILTERS = [
  { key: "ALL",         label: "All" },
  { key: "UNPROCESSED", label: "Unprocessed" },
  { key: "PROCESSED",   label: "Processed" },
];

function outcomeOf(recommendation) {
  if (!recommendation) return null;
  if (recommendation === "WORKABLE") return "workable";
  if (recommendation.startsWith("RETURN_TO_ONSHORE")) return "unworkable";
  return "other";
}

export default function CaseList({ cases = [], runs = {}, error = null, onSelect, selectedId }) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases.filter((c) => {
      const processed = Boolean(runs[c.exception_id]);
      if (statusFilter === "PROCESSED"   && !processed) return false;
      if (statusFilter === "UNPROCESSED" &&  processed) return false;
      if (!q) return true;
      return (
        (c.exception_id   || "").toLowerCase().includes(q) ||
        (c.account_number || "").toLowerCase().includes(q) ||
        (c.exception_type || "").toLowerCase().includes(q)
      );
    });
  }, [cases, runs, query, statusFilter]);

  return (
    <div className="case-list">
      <h2>Cases</h2>

      <input
        type="text"
        className="case-search"
        placeholder="Search id, account, type…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="case-filters">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            className={`filter-pill ${statusFilter === f.key ? "active" : ""}`}
            onClick={() => setStatusFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="case-count">
        {filtered.length} of {cases.length}
      </div>

      {error && <p className="error">{error}</p>}

      <ul>
        {filtered.map((c) => {
          const outcome = outcomeOf(runs[c.exception_id]);
          return (
            <li
              key={c.exception_id}
              className={c.exception_id === selectedId ? "case-row selected" : "case-row"}
              onClick={() => onSelect(c)}
            >
              <div className="case-id">{c.exception_id}</div>
              <div className="case-meta">
                {c.exception_type}
                {outcome && (
                  <span className={`result-chip result-${outcome}`}>
                    {outcome === "workable" ? "Workable" : outcome === "unworkable" ? "Unworkable" : "Processed"}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
