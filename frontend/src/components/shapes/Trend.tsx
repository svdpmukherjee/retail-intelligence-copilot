import { timeValue, type Metric } from "../../answer";

const W = 320;
const H = 92;
const PAD = 8;

export default function Trend({ metrics, caption = "Value" }: { metrics: Metric[]; caption?: string }) {
  const vals = metrics.map((m) => m.value);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const times = metrics.map((m) => timeValue(m.label));
  const firstTime = times[0], timeSpan = times[times.length-1] - firstTime || 1;
  const px = (i: number) => PAD + (times[i]-firstTime) / timeSpan * (W-2*PAD);
  const py = (v: number) => H - PAD - ((v - lo) / span) * (H - 2 * PAD);
  const pts = vals.map((v, i) => `${px(i)},${py(v)}`).join(" ");
  const area = `M${px(0)},${H - PAD} L${pts.split(" ").join(" L")} L${px(vals.length - 1)},${H - PAD} Z`;
  const first = vals[0];
  const last = vals[vals.length - 1];
  const dir = last > first ? "rising" : last < first ? "falling" : "flat";
  const label = `${caption} over time: ${metrics.map((m) => `${m.label}: ${m.value}`).join(", ")}`;
  return (
    <div className="datacard trend">
      <div className="dc-h">
        <span className="h">{caption} over time</span>
        <span className="src">Calculated data</span>
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
