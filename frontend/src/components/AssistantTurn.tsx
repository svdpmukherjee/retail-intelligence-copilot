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
  onCiteClick: (n: number) => void;
}

// Shape is presentation only: all shapes render the same grounded answer.
// Unknown roles fall through to DefaultShape. Charts need "sql" in audit.sources.
const SHAPES = { support: SupportShape, marketing: MarketingShape, executive: ExecutiveShape };

export default function AssistantTurn({ res, state, onCiteClick }: Props) {
  const { audit, citations } = res;
  const lines = splitClaims(res.answer);
  const Shape = SHAPES[audit.role as keyof typeof SHAPES] ?? DefaultShape;
  const suppressCharts = state === "degraded-SQL" || !audit.sources.includes("sql");
  return (
    <div className="turn turn-assistant" data-state={state}>
      <ScopeRibbon scope={audit.scope} />
      {state === "degraded-SQL" && (
        <div className="banner banner-warn" role="status">
          {SQL_DEGRADED}
        </div>
      )}
      {state === "fallback" && <p className="muted">{FALLBACK_NOTE}</p>}
      {state === "no-evidence" ? (
        <div className="calm">
          <p>{NO_EVIDENCE}</p>
        </div>
      ) : (
        <>
          <Shape res={res} lines={lines} suppressCharts={suppressCharts} onCiteClick={onCiteClick} />
          <CitationChips citations={citations} onCiteClick={onCiteClick} />
        </>
      )}
      <TrustStrip audit={audit} fallback={state === "fallback"} />
    </div>
  );
}
