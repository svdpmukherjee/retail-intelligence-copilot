import ClaimLine from "../ClaimLine";
import type { ShapeProps } from "./types";

const FIX = /\b(fix|resolve|resolution|replace|refund|reset|repair)/i;
const POLICY = /policy|manual|guide|warranty|procedure/i;

export default function SupportShape({ res, lines, onCiteClick }: ShapeProps) {
  const policy = res.citations.find((c) => c.source_id !== "sql" && POLICY.test(`${c.source_id} ${c.label}`));
  return (
    <div className="shape shape-support">
      {lines.map((l, i) => {
        const fix = FIX.test(l);
        return (
          <div key={i} className="kv">
            <span className={`k${fix ? " fix" : ""}`}>{fix ? "FIX" : "ISSUE"}</span>
            <ClaimLine line={l} variant="t" onCiteClick={onCiteClick} />
          </div>
        );
      })}
      {policy && (
        <aside className="policy" aria-label="Governing policy">
          <div className="ph">
            <span aria-hidden="true">&#128220;</span> Governing policy &middot; {policy.label}
          </div>
          {policy.snippet && (
            <div className="pq">
              &ldquo;{policy.snippet}&rdquo;{" "}
              <button
                type="button"
                className="cmark"
                aria-label={`Show evidence ${policy.n}`}
                onClick={() => onCiteClick(policy.n)}
              >
                [{policy.n}]
              </button>
            </div>
          )}
        </aside>
      )}
    </div>
  );
}
