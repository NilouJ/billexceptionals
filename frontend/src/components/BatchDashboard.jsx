import { useMemo, useState } from "react";

function summarise(runs) {
  const values = Object.values(runs);
  const processed = values.length;
  const workable = values.filter((r) => r === "WORKABLE").length;
  const unworkable = values.filter((r) => typeof r === "string" && r.startsWith("RETURN_TO_ONSHORE")).length;
  return { processed, workable, unworkable };
}

export default function BatchDashboard({ batchSize = 0, runs = {}, onReset }) {
  const [open, setOpen] = useState(true);
  const { processed, workable, unworkable } = useMemo(() => summarise(runs), [runs]);

  const remaining = Math.max(0, batchSize - processed);
  const pct = batchSize > 0 ? Math.round((processed / batchSize) * 100) : 0;

  const handleReset = () => {
    if (processed === 0) {
      onReset?.();
      return;
    }
    if (window.confirm("Reset the demo counters? Processed cases will be cleared.")) {
      onReset?.();
    }
  };

  return (
    <section className={`batch-dashboard ${open ? "open" : "closed"}`}>
      <button
        type="button"
        className="batch-dashboard-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="batch-dashboard-chevron">{open ? "▾" : "▸"}</span>
        <span className="batch-dashboard-title">Batch overview</span>
        <span className="batch-dashboard-summary">
          {processed} / {batchSize} processed · {pct}%
        </span>
      </button>

      {open && (
        <div className="batch-dashboard-body">
          <div className="batch-tiles">
            <Tile label="Batch size"  value={batchSize}  tone="neutral" />
            <Tile label="Processed"   value={processed}  tone="accent"  sub={`${remaining} remaining`} />
            <Tile label="Workable"    value={workable}   tone="ok" />
            <Tile label="Unworkable"  value={unworkable} tone="warn" />
          </div>

          <button
            type="button"
            className="batch-reset"
            onClick={handleReset}
            disabled={processed === 0}
            title="Clear processed counters (demo only)"
          >
            Reset demo
          </button>
        </div>
      )}
    </section>
  );
}

function Tile({ label, value, sub, tone = "neutral" }) {
  return (
    <div className={`batch-tile tone-${tone}`}>
      <div className="batch-tile-label">{label}</div>
      <div className="batch-tile-value">{value}</div>
      {sub && <div className="batch-tile-sub">{sub}</div>}
    </div>
  );
}
