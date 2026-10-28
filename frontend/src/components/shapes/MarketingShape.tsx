import ClaimLine from "../ClaimLine";
import { sqlMetrics } from "../../answer";
import Trend from "./Trend";
import type { ShapeProps } from "./types";

export default function MarketingShape({ res, lines, suppressCharts, onCiteClick }: ShapeProps) {
  const metrics = suppressCharts ? [] : sqlMetrics(lines, res.citations);
  return (
    <div className="shape shape-marketing">
      <h2>Themes</h2>
      {lines.map((l, i) => (
        <ClaimLine key={i} line={l} onCiteClick={onCiteClick} />
      ))}
      {metrics.length >= 2 && <Trend metrics={metrics} />}
    </div>
  );
}
