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
      {headline && <div className="headline"><ClaimLine line={headline} onCiteClick={onCiteClick} /></div>}
      {metrics.length > 0 && <Bars metrics={metrics} caption="Ranked metric from SQL" />}
      {body.map((l, i) => (
        <ClaimLine key={i} line={l} onCiteClick={onCiteClick} />
      ))}
      {cause && <ClaimLine line={cause} onCiteClick={onCiteClick} />}
    </div>
  );
}
