import { useEffect, useMemo, useState } from "react";
import { fetchCases } from "../api/rest.js";

const ROUTING_FILTERS = [
  { key: "ALL",      label: "All" },
  { key: "WORKABLE", label: "Workable" },
  { key: "ONSHORE",  label: "Onshore" },
];

export default function CaseList({ onSelect, selectedId }) {
  const [cases, setCases] = useState([]);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [routing, setRouting] = useState("ALL");

  useEffect(() => {
    fetchCases().then(setCases).catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cases.filter((c) => {
      if (routing !== "ALL" && (c.gt_final_routing || "") !== routing) return false;
      if (!q) return true;
      return (
        (c.exception_id     || "").toLowerCase().includes(q) ||
        (c.account_number   || "").toLowerCase().includes(q) ||
        (c.exception_type   || "").toLowerCase().includes(q) ||
        (c.gt_final_routing || "").toLowerCase().includes(q)
      );
    });
  }, [cases, query, routing]);

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
        {ROUTING_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            className={`filter-pill ${routing === f.key ? "active" : ""}`}
            onClick={() => setRouting(f.key)}
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
        {filtered.map((c) => (
          <li
            key={c.exception_id}
            className={c.exception_id === selectedId ? "case-row selected" : "case-row"}
            onClick={() => onSelect(c)}
          >
            <div className="case-id">{c.exception_id}</div>
            <div className="case-meta">
              {c.exception_type}
              {c.gt_final_routing && <span className={`gt-chip gt-${(c.gt_final_routing || "").toLowerCase()}`}>{c.gt_final_routing}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
