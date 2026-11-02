import type { SqlBlock } from "./api/types";

export type Segment = { kind: "text"; text: string } | { kind: "cite"; n: number };

const CITE = /\[(\d+)\]/g;

// One claim per line (composer contract); blank lines carry no claim.
export function splitClaims(answer: string): string[] {
  return answer
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

// Splits a line into text runs and [n] markers so markers render as buttons.
export function parseLine(line: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of line.matchAll(CITE)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ kind: "text", text: line.slice(last, at) });
    out.push({ kind: "cite", n: Number(m[1]) });
    last = at + m[0].length;
  }
  if (last < line.length) out.push({ kind: "text", text: line.slice(last) });
  return out;
}

export function stripCites(line: string): string {
  return line.replace(CITE, "").replace(/\s+/g, " ").trim();
}

export function citedNumbers(line: string): number[] {
  return Array.from(line.matchAll(CITE), (m) => Number(m[1]));
}

export interface Metric {
  label: string;
  value: number;
  n: number;
}

const YEAR_NAME = /(^|_)(year|yr|month|date|period)($|_)/i;

// A chart earns its place only when there is something to compare: fewer rows read better as a
// sentence or a small table, so a 1-2 row result is never charted (the over-visualisation fix).
const MIN_CHART_ROWS = 3;

const isNum = (v: unknown): v is number => typeof v === "number";

// A year-like column (named so, or all integers in 1900-2100) is a label, not a measure.
function isYearLike(name: string, cells: unknown[]): boolean {
  return (
    YEAR_NAME.test(name) ||
    cells.every((v) => isNum(v) && Number.isInteger(v) && v >= 1900 && v <= 2100)
  );
}

// Chart metrics straight from the typed SQL rows (never parsed from prose). Charts are drawn
// only when unambiguous: exactly one all-numeric, non-year-like column is the measure, and
// another column (first non-measure) labels each row. Anything else returns [] -> table only.
export function sqlBlockMetrics(block: SqlBlock | null): Metric[] {
  if (!block || block.rows.length < MIN_CHART_ROWS) return [];
  const col = (i: number) => block.rows.map((r) => r[i]);
  const numeric = block.columns
    .map((name, i) => ({ name, i, cells: col(i) }))
    .filter(({ cells }) => cells.every(isNum));
  const measures = numeric.filter(({ name, cells }) => !isYearLike(name, cells));
  if (measures.length !== 1 || block.columns.length < 2) return [];
  const measure = measures[0].i;
  const values = block.rows.map((r) => r[measure] as number);
  // All-equal measures (e.g. every category returned the same count) have nothing to compare.
  if (new Set(values).size < 2) return [];
  const label = block.columns.findIndex((_, i) => i !== measure);
  return block.rows.map((r, i) => ({
    label: String(r[label] ?? ""),
    value: values[i],
    n: 1, // the SQL block is always citation [1]
  }));
}
