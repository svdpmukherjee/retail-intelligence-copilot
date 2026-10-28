import { useState } from "react";
import type { Audit } from "../api/types";

const GROUNDING_LABEL: Record<Audit["grounding"]["path"], string> = {
  llm: "grounded (llm)",
  extractive: "grounded (extractive)",
  none: "none (unsupported)",
};
const GROUNDING_EXPLAIN: Record<Audit["grounding"]["path"], string> = {
  llm: "model-written, cite-checked",
  extractive: "verbatim extract from sources",
  none: "no supporting evidence",
};
const GROUND_CLASS: Record<Audit["grounding"]["path"], string> = { llm: "", extractive: "partial", none: "none" };

interface Props {
  audit: Audit;
  fallback: boolean;
}

function Field({ k, v, tone, wide }: { k: string; v: string; tone?: "good" | "warn"; wide?: boolean }) {
  return (
    <div className={`f${wide ? " wide" : ""}`}>
      <div className="k">{k}</div>
      <div className={`v${tone ? ` ${tone}` : ""}`}>{v}</div>
    </div>
  );
}

export default function TrustStrip({ audit, fallback }: Props) {
  const [open, setOpen] = useState(false);
  const g = audit.grounding;
  const groundCls = fallback ? "partial" : GROUND_CLASS[g.path];
  const sources = audit.sources.length;
  return (
    <section className="trust" aria-label="Trust details">
      <button type="button" className="th" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="pill route">&#8683; {audit.intent}</span>
        <span className={`pill ground ${groundCls}`}>
          <span className="dot" />
          {GROUNDING_LABEL[g.path]}
        </span>
        <span className="pill">&#9201; {audit.latency_ms}ms</span>
        <span className="pill cost">${audit.cost_usd.toFixed(audit.cost_usd ? 4 : 2)}</span>
        <span className="caret">
          {open ? "hide" : "why"} <span aria-hidden="true">{open ? "▴" : "▾"}</span>
        </span>
        {g.issues.length > 0 && <span className="fallback-note">&#9888; fallback: {g.issues[0]}</span>}
      </button>
      <div className="tbody" hidden={!open}>
        <Field k="Route" v={audit.intent} />
        <Field k="Tool path" v={audit.tool_path.join(" → ")} />
        <Field k="Grounding" v={`${GROUNDING_LABEL[g.path]} — ${GROUNDING_EXPLAIN[g.path]}`} />
        <Field
          k="Evidence used"
          v={`${sources} source${sources === 1 ? "" : "s"}${sources ? ` (${audit.sources.join(", ")})` : ""}`}
        />
        <Field k="Tokens" v={audit.tokens.toLocaleString()} />
        <Field k="Cost" v={`$${audit.cost_usd.toFixed(audit.cost_usd ? 4 : 2)}`} tone="good" />
        <Field k="Latency" v={`${audit.latency_ms} ms`} />
        <Field
          k="Memory"
          v={
            audit.memory
              ? `used ${audit.memory.history_turns_used} prior turn${audit.memory.history_turns_used === 1 ? "" : "s"} · persisted ${audit.memory.persisted}`
              : "off for this turn"
          }
        />
        {audit.sql_error && (
          <Field k="SQL error" v={`⚠ ${audit.sql_error} — answer leans on remaining evidence`} tone="warn" wide />
        )}
        {g.issues.length > 0 && <Field k="Grounding issues" v={g.issues.join(" · ")} tone="warn" wide />}
      </div>
    </section>
  );
}
