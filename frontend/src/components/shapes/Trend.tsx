import type { Metric } from "../../answer";

export default function Trend({ metrics }: { metrics: Metric[] }) {
  const vals = metrics.map((m) => m.value);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * 290 + 5},${35 - ((v - lo) / span) * 30}`).join(" ");
  const first = vals[0];
  const last = vals[vals.length - 1];
  const dir = last > first ? "rising" : last < first ? "falling" : "flat";
  const label = `Sentiment trend ${dir} from ${first} to ${last}`;
  return (
    <figure className="trend">
      <svg role="img" aria-label={label} viewBox="0 0 300 40" className="spark">
        <title>{label}</title>
        <polyline points={pts} fill="none" stroke="var(--accent)" strokeWidth="2" />
      </svg>
      <figcaption className="muted">from SQL</figcaption>
    </figure>
  );
}
