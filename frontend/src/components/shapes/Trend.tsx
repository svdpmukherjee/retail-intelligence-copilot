import type { Metric } from "../../answer";

const W = 320;
const H = 92;
const PAD = 8;

export default function Trend({ metrics }: { metrics: Metric[] }) {
  const vals = metrics.map((m) => m.value);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const px = (i: number) => PAD + i * ((W - 2 * PAD) / (vals.length - 1));
  const py = (v: number) => H - PAD - ((v - lo) / span) * (H - 2 * PAD);
  const pts = vals.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const area = `M${px(0)},${H - PAD} L${pts.split(" ").join(" L")} L${px(vals.length - 1)},${H - PAD} Z`;
  const first = vals[0];
  const last = vals[vals.length - 1];
  const dir = last > first ? "rising" : last < first ? "falling" : "flat";
  const label = `Sentiment trend ${dir} from ${first} to ${last}`;
  return (
    <div className="datacard trend">
      <div className="dc-h">
        <span className="h">Trend</span>
        <span className="src">source: SQL</span>
      </div>
      <svg role="img" aria-label={label} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <title>{label}</title>
        <path d={area} fill="var(--c2)" fillOpacity="0.14" />
        <polyline points={pts} fill="none" stroke="var(--c2)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {vals.map((v, i) => (
          <circle key={i} cx={px(i)} cy={py(v)} r="3" fill="var(--c2)" />
        ))}
      </svg>
      <div className="cap">
        {first} &rarr; <b>{last} &middot; {dir}</b>
      </div>
    </div>
  );
}
