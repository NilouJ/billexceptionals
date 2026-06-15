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

export default function CaseList({
  cases = [],
  runs = {},
  error = null,
  onSelect,
  selectedId,
  total = 0,
  page = 1,
  pages = 1,
  onPageChange,
  search = "",
  onSearch,
}) {
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Status filter is session-local — applied to the current page only
  const visible = useMemo(() => {
    return cases.filter((c) => {
      const processed = Boolean(runs[c.exception_id]);
      if (statusFilter === "PROCESSED"   && !processed) return false;
      if (statusFilter === "UNPROCESSED" &&  processed) return false;
      return true;
    });
  }, [cases, runs, statusFilter]);

  return (
    <div className="case-list">
      <h2>Cases</h2>

      <input
        type="text"
        className="case-search"
        placeholder="Search id, account, type…"
        value={search}
        onChange={(e) => onSearch(e.target.value)}
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
        {visible.length} shown · {total} total
      </div>

      {error && <p className="error">{error}</p>}

      <ul>
        {visible.map((c) => {
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

      {pages > 1 && (
        <div className="pagination">
          <button
            className="page-btn"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            ‹
          </button>

          {Array.from({ length: pages }, (_, i) => i + 1)
            .filter((p) => p === 1 || p === pages || Math.abs(p - page) <= 1)
            .reduce((acc, p, idx, arr) => {
              if (idx > 0 && p - arr[idx - 1] > 1) acc.push("…");
              acc.push(p);
              return acc;
            }, [])
            .map((p, i) =>
              p === "…" ? (
                <span key={`ellipsis-${i}`} className="page-ellipsis">…</span>
              ) : (
                <button
                  key={p}
                  className={`page-btn${p === page ? " active" : ""}`}
                  onClick={() => onPageChange(p)}
                >
                  {p}
                </button>
              )
            )}

          <button
            className="page-btn"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

