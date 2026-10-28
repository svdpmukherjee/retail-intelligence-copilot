import type { Audit } from "../api/types";

interface Props {
  audit: Audit | null;
  threadId: string | null;
  userId: string;
}

function Row({ k, v, good }: { k: string; v: string; good?: boolean }) {
  return (
    <div className="r">
      <span className="k">{k}</span>
      <span className={`v${good ? " good" : ""}`}>{v}</span>
    </div>
  );
}

export default function SessionCard({ audit, threadId, userId }: Props) {
  return (
    <section className="card" aria-label="Session">
      <h2>Session</h2>
      <div className="session">
        <Row k="Cost" v={audit ? `$${audit.cost_usd.toFixed(4)}` : "—"} good />
        <Row k="Tokens" v={audit ? String(audit.tokens) : "—"} />
        <Row k="Latency" v={audit ? `${audit.latency_ms} ms` : "—"} />
        <Row k="Thread" v={threadId ?? "—"} />
        <Row k="User" v={userId} />
        <Row k="Provider" v="invisible" />
      </div>
    </section>
  );
}
