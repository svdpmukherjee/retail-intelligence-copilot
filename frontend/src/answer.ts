import type { SqlBlock } from "./api/types";

export type Segment = { kind: "text"; text: string } | { kind: "cite"; n: number };

const CITE = /\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]/g;

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
    for (const n of m[1].split(",")) out.push({ kind: "cite", n: Number(n.trim()) });
    last = at + m[0].length;
  }
  if (last < line.length) out.push({ kind: "text", text: line.slice(last) });
  return out;
}

export function stripCites(line: string): string {
  return line.replace(CITE, "").trim();
}

export function citedNumbers(line: string): number[] {
  return Array.from(line.matchAll(CITE)).flatMap((m) => m[1].split(",").map((n) => Number(n.trim())));
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

export function timeValue(label: string): number {
  if (/^\d{4}$/.test(label)) return Number(label);
  if (!/^\d{4}-\d{2}(?:-\d{2})?$/.test(label)) return NaN;
  const value = Date.parse(label);
  return Number.isFinite(value) && new Date(value).toISOString().slice(0,label.length) === label ? value : NaN;
}

export interface SqlChart { kind: "comparison" | "time"; caption: string; metrics: Metric[] }

export function sqlChart(block: SqlBlock | null): SqlChart | null {
  if (!block || block.has_more || block.total_rows !== block.rows.length ||
      block.rows.length < MIN_CHART_ROWS || block.columns.length !== 2) return null;
  const numeric = block.columns.map((_, i) => i).filter((i) =>
    block.rows.every((row) => isNum(row[i]) && Number.isFinite(row[i])) &&
    !YEAR_NAME.test(block.columns[i]));
  if (numeric.length !== 1) return null;
  const measure = numeric[0], label = 1 - measure;
  if (!block.rows.every((r) => r[label] !== null) ||
      new Set(block.rows.map((r) => String(r[label]))).size !== block.rows.length) return null;
  const metrics = block.rows.map((r) => ({ label: String(r[label]).replaceAll("_", " "), value: r[measure] as number, n: 1 }));
  const caption = block.columns[measure].replaceAll("_", " ");
  if (YEAR_NAME.test(block.columns[label])) {
    if (new Set(metrics.map((m) => m.label.length)).size !== 1) return null;
    if (metrics.some((m) => !Number.isFinite(timeValue(m.label)))) return null;
    return { kind: "time", caption, metrics: metrics.sort((a,b) => timeValue(a.label)-timeValue(b.label)) };
  }
  if (!/^(category|product_title)$/i.test(block.columns[label]) || metrics.some((m) => m.value < 0)) return null;
  if (new Set(metrics.map((m) => m.value)).size < 2) return null;
  return { kind: "comparison", caption, metrics: metrics.sort((a,b) => b.value-a.value || a.label.localeCompare(b.label)) };
}

export function sqlBlockMetrics(block: SqlBlock | null): Metric[] {
  return sqlChart(block)?.metrics ?? [];
}
