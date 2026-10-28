import ClaimLine from "../ClaimLine";
import { sqlMetrics } from "../../answer";
import { Themes } from "./Bars";
import Trend from "./Trend";
import type { ShapeProps } from "./types";

export default function MarketingShape({ res, lines, suppressCharts, onCiteClick }: ShapeProps) {
  const metrics = suppressCharts ? [] : sqlMetrics(lines, res.citations);
  return (
    <div className="shape shape-marketing">
      {lines.map((l, i) => (
        <ClaimLine key={i} line={l} onCiteClick={onCiteClick} />
      ))}
      {metrics.length > 0 && (
        <div className="datacard">
          <div className="dc-h">
            <span className="h">Themes</span>
            <span className="src">source: SQL</span>
          </div>
          <Themes metrics={metrics} caption="Themes from SQL" />
        </div>
      )}
      {metrics.length >= 2 && <Trend metrics={metrics} />}
    </div>
  );
}
