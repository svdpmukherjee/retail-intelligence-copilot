import type { Metric } from "../../answer";

export const CHART_COLORS = ["var(--c1)", "var(--c2)", "var(--c3)"];

function words(metrics: Metric[]): string {
  return metrics.map((m) => `${m.label} ${m.value}`).join(", ");
}

// Ranked rows (executive). The aria-label states the data in words; the same
// fact is also carried by the answer text above.
export function Ranked({ metrics, caption }: { metrics: Metric[]; caption: string }) {
  const max = Math.max(...metrics.map((m) => m.value), 1);
  return (
    <div className="ranked" role="img" aria-label={`${caption}: ${words(metrics)}`}>
      {metrics.map((m, i) => (
        <div key={i} className="rrow">
          <div className="rk">{i + 1}</div>
          <div className="rl" title={m.label}>{m.label}</div>
          <div className="track">
            <div className="fill" style={{ width: `${(m.value / max) * 100}%`, background: CHART_COLORS[i % CHART_COLORS.length] }} />
          </div>
          <div className="rv">{m.value}</div>
        </div>
      ))}
    </div>
  );
}

// Labelled share rows (marketing themes).
export function Themes({ metrics, caption }: { metrics: Metric[]; caption: string }) {
  const max = Math.max(...metrics.map((m) => m.value), 1);
  return (
    <div className="themes" role="img" aria-label={`${caption}: ${words(metrics)}`}>
      {metrics.map((m, i) => (
        <div key={i} className="theme-row">
          <div className="tl" title={m.label}>{m.label}</div>
          <div className="track">
            <div className="fill" style={{ width: `${(m.value / max) * 100}%`, background: CHART_COLORS[i % CHART_COLORS.length] }} />
          </div>
          <div className="tv">{m.value}</div>
        </div>
      ))}
    </div>
  );
}

export default Ranked;
