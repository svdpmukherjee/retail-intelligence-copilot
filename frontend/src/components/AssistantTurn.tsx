import type { QueryResponse } from "../api/types";
import type { PanelState } from "../panelState";
import { splitClaims, stripCites } from "../answer";
import { FALLBACK_NOTE, HISTORICAL_NOTE, NO_EVIDENCE, SQL_DEGRADED } from "../copy";
import CitationChips from "./CitationChips";
import ScopeRibbon from "./ScopeRibbon";
import TrustStrip from "./TrustStrip";
import DefaultShape from "./shapes/DefaultShape";
import ExecutiveShape from "./shapes/ExecutiveShape";
import MarketingShape from "./shapes/MarketingShape";
import SupportShape from "./shapes/SupportShape";

interface LiveProps {
  res: QueryResponse;
  state: PanelState;
  activeN?: number | null;
  onCiteClick: (n: number) => void;
  historical?: undefined;
}

// A restored turn: stored redacted text only. No res, so no strip, chips or evidence.
interface HistoricalProps {
  historical: { role: string; content: string };
  res?: undefined;
}

type Props = LiveProps | HistoricalProps;

// Shape is presentation only: all shapes render the same grounded answer.
// Unknown roles fall through to DefaultShape. Charts need "sql" in audit.sources.
const SHAPES = { support: SupportShape, marketing: MarketingShape, executive: ExecutiveShape };

function HistoricalTurn({ role, content }: { role: string; content: string }) {
  // Markers point at evidence that was not kept, so they are dropped, not linked.
  const lines = splitClaims(content).map(stripCites);
  return (
    <div className="turn bot historical" data-state="historical">
      <div className="av" aria-hidden="true">
        R
      </div>
      <div className="body">
        <div className="answer">
          <div className={`shape shape-${role in SHAPES ? role : "default"}`}>
            {lines.map((l, i) => (
              <p key={i} className="line">
                {l}
              </p>
            ))}
          </div>
          <div className="hist-note" role="note">
            {HISTORICAL_NOTE}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AssistantTurn(props: Props) {
  if (props.historical) return <HistoricalTurn {...props.historical} />;
  const { res, state, activeN = null, onCiteClick } = props;
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
