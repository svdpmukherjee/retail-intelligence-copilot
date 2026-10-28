import type { Citation } from "./api/types";

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

// Metrics come only from claim lines that cite the SQL result; the number is
// read out of the answer text, never invented.
export function sqlMetrics(lines: string[], citations: Citation[]): Metric[] {
  const sqlNs = new Set(citations.filter((c) => c.source_id === "sql").map((c) => c.n));
  const metrics: Metric[] = [];
  for (const line of lines) {
    const n = citedNumbers(line).find((x) => sqlNs.has(x));
    if (n === undefined) continue;
    const text = stripCites(line);
    const num = text.match(/\d+(?:\.\d+)?/);
    if (!num) continue;
    const label = text.replace(num[0], "").replace(/[:\-–()]+/g, " ").replace(/\s+/g, " ").trim();
    metrics.push({ label: label || `Result ${n}`, value: Number(num[0]), n });
  }
  return metrics;
}
