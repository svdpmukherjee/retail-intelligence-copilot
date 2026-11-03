import type { SqlBlock } from "../../api/types";

// The exact SQL result rows (citation [1]); default view when charts are not derivable.
export default function SqlTable({ block }: { block: SqlBlock }) {
  const columns = block.columns.map((name, index) => ({ name, index }))
    .filter(({ name }) => name !== "asin" || !block.columns.includes("product_title"));
  const label = (name: string) => ({ avg_rating: "Average rating", review_count: "Review count", product_title: "Product", category: "Category" }[name] ?? name.replaceAll("_", " "));
  return (
    <div className="datacard">
      <div className="dc-h">
        <span className="h">Result</span>
        <span className="src">
          Calculated data
          {block.has_more
            ? ` · showing ${block.rows.length} of at least ${block.total_rows + 1} matches`
            : block.total_rows > block.rows.length
            ? ` · showing ${block.rows.length} of ${block.total_rows}`
            : ""}
        </span>
      </div>
      <table className="sqltable" aria-label="SQL result">
        <thead>
          <tr>
            {columns.map(({ name: c, index: i }) => (
              <th key={i} scope="col">{label(c)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((r, i) => (
            <tr key={i}>
              {columns.map(({ index: j }) => (
                <td key={j}>{r[j] === null ? "" : block.columns[j] === "category" ? String(r[j]).replaceAll("_", " ") : String(r[j])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
