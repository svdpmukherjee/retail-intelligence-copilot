import type { Metric } from "../../answer";

// Labelled SVG; the aria-label states the data in words. The same fact is
// also carried by the answer text above.
export default function Bars({ metrics, caption }: { metrics: Metric[]; caption: string }) {
  const max = Math.max(...metrics.map((m) => m.value), 1);
  const h = 22;
  const words = metrics.map((m) => `${m.label} ${m.value}`).join(", ");
  return (
    <svg role="img" aria-label={`${caption}: ${words}`} viewBox={`0 0 300 ${metrics.length * h}`} className="bars">
      <title>{`${caption}: ${words}`}</title>
      {metrics.map((m, i) => (
        <g key={i} transform={`translate(0 ${i * h})`}>
          <rect x="0" y="3" height="14" width={(m.value / max) * 290} rx="3" fill="var(--accent)" />
        </g>
      ))}
    </svg>
  );
}
