import { useState } from "react";
import type { Audit } from "../api/types";

const GROUNDING_EXPLAIN: Record<Audit["grounding"]["path"], string> = {
  llm: "model-written, cite-checked",
  extractive: "verbatim extract",
  none: "no supporting evidence",
};

interface Props {
  audit: Audit;
  fallback: boolean;
}

export default function TrustStrip({ audit, fallback }: Props) {
  const [open, setOpen] = useState(false);
  const g = audit.grounding;
  return (
    <section className="trust" aria-label="Trust details">
      <div className="trust-head">
        <span className={`pill pill-${g.path}`}>{g.path}</span>
        <span className="muted">
          {audit.intent} · {g.path} · {audit.latency_ms} ms · ${audit.cost_usd.toFixed(audit.cost_usd ? 4 : 0)} cost
          {fallback ? " · fallback" : ""}
        </span>
        <button type="button" className="link" aria-expanded={open} onClick={() => setOpen(!open)}>
          why {open ? "▴" : "▾"}
        </button>
      </div>
      {open && (
        <dl className="kv">
          <dt>Path</dt>
          <dd>{audit.tool_path.join(" → ")}</dd>
          <dt>Grounding</dt>
          <dd>{GROUNDING_EXPLAIN[g.path]}</dd>
          <dt>Sources</dt>
          <dd>
            {audit.sources.length} <span className="mono">{audit.sources.join(", ")}</span>
          </dd>
          <dt>Tokens</dt>
          <dd>{audit.tokens}</dd>
          <dt>Memory</dt>
          <dd>
            {audit.memory
              ? `${audit.memory.history_turns_used} turns used · ${audit.memory.persisted} persisted`
              : "off for this turn"}
          </dd>
          {audit.sql_error && (
            <>
              <dt>SQL error</dt>
              <dd>{audit.sql_error}</dd>
            </>
          )}
          {g.issues.length > 0 && (
            <>
              <dt>Issues</dt>
              <dd>{g.issues.join("; ")}</dd>
            </>
          )}
        </dl>
      )}
    </section>
  );
}
