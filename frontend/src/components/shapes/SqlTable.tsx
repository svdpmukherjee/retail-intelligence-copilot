import type { SqlBlock } from "../../api/types";

// The exact SQL result rows (citation [1]); default view when charts are not derivable.
export default function SqlTable({ block }: { block: SqlBlock }) {
  return (
    <div className="datacard">
      <div className="dc-h">
        <span className="h">Result</span>
        <span className="src">
          source: SQL
          {block.total_rows > block.rows.length
            ? ` · showing ${block.rows.length} of ${block.total_rows}`
            : ""}
        </span>
      </div>
      <table className="sqltable" aria-label="SQL result">
        <thead>
          <tr>
            {block.columns.map((c, i) => (
              <th key={i} scope="col">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (
                <td key={j}>{v === null ? "" : String(v)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
