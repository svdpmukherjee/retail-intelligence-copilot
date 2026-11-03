import { sqlChart } from "../../answer";
import type { SqlBlock } from "../../api/types";
import { Themes } from "./Bars";
import SqlTable from "./SqlTable";
import Trend from "./Trend";

export default function SqlData({ block }: { block: SqlBlock }) {
  const chart = sqlChart(block);
  if (!chart) return <SqlTable block={block} />;
  return <>
    {chart.kind === "time" ? <Trend metrics={chart.metrics} caption={chart.caption} /> :
      <div className="datacard"><div className="dc-h"><span className="h">Comparison · {chart.caption}</span></div>
        <Themes metrics={chart.metrics} caption={`Comparison of ${chart.caption}`} /></div>}
    <details className="exact-values"><summary>View exact values</summary><SqlTable block={block} /></details>
  </>;
}
