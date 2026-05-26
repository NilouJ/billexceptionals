import { useEffect, useState } from "react";
import { fetchCases } from "../api/rest.js";

export default function CaseList({ onSelect, selectedId }) {
  const [cases, setCases] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCases().then(setCases).catch((e) => setError(e.message));
  }, []);

  return (
    <div className="case-list">
      <h2>Cases</h2>
      {error && <p className="error">{error}</p>}
      <ul>
        {cases.map((c) => (
          <li
            key={c.exception_id}
            className={c.exception_id === selectedId ? "case-row selected" : "case-row"}
            onClick={() => onSelect(c)}
          >
            <div className="case-id">{c.exception_id}</div>
            <div className="case-meta">{c.exception_type}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}