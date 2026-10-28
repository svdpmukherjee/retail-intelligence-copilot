import type { Audit } from "../api/types";

interface Props {
  audit: Audit | null;
  threadId: string | null;
  userId: string;
}

export default function SessionCard({ audit, threadId, userId }: Props) {
  return (
    <section className="card" aria-label="Session">
      <h2>Session</h2>
      <dl className="kv">
        <dt>Cost</dt>
        <dd>{audit ? `$${audit.cost_usd.toFixed(4)}` : "—"}</dd>
        <dt>Tokens</dt>
        <dd>{audit ? audit.tokens : "—"}</dd>
        <dt>Latency</dt>
        <dd>{audit ? `${audit.latency_ms} ms` : "—"}</dd>
        <dt>Thread</dt>
        <dd className="mono">{threadId ?? "—"}</dd>
        <dt>User</dt>
        <dd className="mono">{userId}</dd>
      </dl>
      <p className="muted">Provider: invisible</p>
    </section>
  );
}
