import ClaimLine from "../ClaimLine";
import type { ShapeProps } from "./types";

const FIX = /\b(fix|resolve|resolution|replace|refund|reset|repair)/i;
const POLICY = /policy|manual|guide|warranty|procedure/i;

export default function SupportShape({ res, lines, onCiteClick }: ShapeProps) {
  const policy = res.citations.find((c) => c.source_id !== "sql" && POLICY.test(`${c.source_id} ${c.label}`));
  return (
    <div className="shape shape-support">
      {lines.map((l, i) => (
        <div key={i} className="row">
          <span className={`tag ${FIX.test(l) ? "tag-fix" : "tag-issue"}`}>{FIX.test(l) ? "FIX" : "ISSUE"}</span>
          <ClaimLine line={l} onCiteClick={onCiteClick} />
        </div>
      ))}
      {policy && (
        <aside className="card policy" aria-label="Governing policy">
          <h2>Governing policy</h2>
          <p>{policy.label}</p>
          {policy.snippet && <blockquote>{policy.snippet}</blockquote>}
        </aside>
      )}
    </div>
  );
}
