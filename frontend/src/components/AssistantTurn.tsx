import type { QueryResponse } from "../api/types";
import type { PanelState } from "../panelState";
import { splitClaims } from "../answer";
import { FALLBACK_NOTE, NO_EVIDENCE, SQL_DEGRADED } from "../copy";
import CitationChips from "./CitationChips";
import ScopeRibbon from "./ScopeRibbon";
import TrustStrip from "./TrustStrip";
import DefaultShape from "./shapes/DefaultShape";
import ExecutiveShape from "./shapes/ExecutiveShape";
import MarketingShape from "./shapes/MarketingShape";
import SupportShape from "./shapes/SupportShape";

interface Props {
  res: QueryResponse;
  state: PanelState;
  activeN?: number | null;
  onCiteClick: (n: number) => void;
}

// Shape is presentation only: all shapes render the same grounded answer.
// Unknown roles fall through to DefaultShape. Charts need "sql" in audit.sources.
const SHAPES = { support: SupportShape, marketing: MarketingShape, executive: ExecutiveShape };

export default function AssistantTurn({ res, state, activeN = null, onCiteClick }: Props) {
  const { audit, citations } = res;
  const lines = splitClaims(res.answer);
  const Shape = SHAPES[audit.role as keyof typeof SHAPES] ?? DefaultShape;
  const suppressCharts = state === "degraded-SQL" || !audit.sources.includes("sql");
  return (
    <div className="turn bot" data-state={state}>
      <div className="av" aria-hidden="true">
        R
      </div>
      <div className="body">
        <div className="answer">
          <ScopeRibbon scope={audit.scope} />
          {state === "degraded-SQL" && (
            <div className="warnline" role="status">
              <span className="ic" aria-hidden="true">
                &#9888;
              </span>
              <span>{SQL_DEGRADED}</span>
            </div>
          )}
          {state === "fallback" && (
            <div className="warnline" role="status">
              <span className="ic" aria-hidden="true">
                &#9888;
              </span>
              <span>{FALLBACK_NOTE}</span>
            </div>
          )}
          {state === "no-evidence" ? (
            <div className="noevid">
              <span className="ic" aria-hidden="true">
                &#9675;
              </span>
              <span>{NO_EVIDENCE}</span>
            </div>
          ) : (
            <>
              <Shape res={res} lines={lines} suppressCharts={suppressCharts} onCiteClick={onCiteClick} />
              <CitationChips citations={citations} activeN={activeN} onCiteClick={onCiteClick} />
            </>
          )}
          <TrustStrip audit={audit} fallback={state === "fallback"} />
        </div>
      </div>
    </div>
  );
}
