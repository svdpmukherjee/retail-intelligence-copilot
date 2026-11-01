import ClaimLine from "../ClaimLine";
import { sqlBlockMetrics } from "../../answer";
import { Themes } from "./Bars";
import SqlTable from "./SqlTable";
import Trend from "./Trend";
import type { ShapeProps } from "./types";

export default function MarketingShape({ res, lines, suppressCharts, onCiteClick }: ShapeProps) {
  const metrics = suppressCharts ? [] : sqlBlockMetrics(res.sql);
  return (
    <div className="shape shape-marketing">
      {lines.map((l, i) => (
        <ClaimLine key={i} line={l} onCiteClick={onCiteClick} />
      ))}
      {!suppressCharts && res.sql && metrics.length === 0 && <SqlTable block={res.sql} />}
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
