import ClaimLine from "../ClaimLine";
import { sqlMetrics } from "../../answer";
import Bars from "./Bars";
import type { ShapeProps } from "./types";

export default function ExecutiveShape({ res, lines, suppressCharts, onCiteClick }: ShapeProps) {
  const metrics = suppressCharts ? [] : sqlMetrics(lines, res.citations);
  const [headline, ...rest] = lines;
  const cause = rest.length > 0 ? rest[rest.length - 1] : null;
  const body = rest.slice(0, -1);
  return (
    <div className="shape shape-executive">
      {headline && <ClaimLine line={headline} variant="quote" onCiteClick={onCiteClick} />}
      {metrics.length > 0 && (
        <div className="datacard">
          <div className="dc-h">
            <span className="h">Ranked metric</span>
            <span className="src">source: SQL</span>
          </div>
          <Bars metrics={metrics} caption="Ranked metric from SQL" />
        </div>
      )}
      {body.map((l, i) => (
        <ClaimLine key={i} line={l} onCiteClick={onCiteClick} />
      ))}
      {cause && <ClaimLine line={cause} onCiteClick={onCiteClick} />}
    </div>
  );
}
