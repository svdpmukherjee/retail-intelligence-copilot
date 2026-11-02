import { useEffect, useState } from "react";
import { getAudit } from "../api/client";
import type { AuditListResponse } from "../api/types";
import { IDENTITIES, Identity, relativeTime } from "../identities";
import { errorMessage } from "../panelState";
import AuditDetail from "./AuditDetail";
import "./admin.css";

const PAGE = 20;

interface Props {
  identity: Identity;
  onIdentity: (next: Identity) => void;
}

export default function AuditView({ identity, onIdentity }: Props) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<AuditListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let live = true;
    setError(null);
    getAudit(identity.role, PAGE, offset)
      .then((d) => live && setData(d))
      .catch((err) => {
        if (!live) return;
        setData(null);
        setError(errorMessage(err));
      });
    return () => {
      live = false;
    };
  }, [identity.role, offset, reload]);

  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE, total);

  return (
    <div className="adm">
      <header className="adm-head">
        <h1>Audit log</h1>
        <select
          aria-label="Identity"
          value={identity.userId}
          onChange={(e) => {
            const next = IDENTITIES.find((i) => i.userId === e.target.value);
            if (next) onIdentity(next);
          }}
        >
          {IDENTITIES.map((i) => (
            <option key={i.userId} value={i.userId}>
              {i.userId} ({i.role})
            </option>
          ))}
        </select>
      </header>
      <p className="adm-sub">
        Per-answer governance trail. Tokens/cost are the LLM's actual prompt + completion usage
        (summed across the calls each answer makes); local embeddings run at $0. Click a row to
        reconstruct the full query&nbsp;&rarr;&nbsp;output.
      </p>
      {error && (
        <div role="alert" className="adm-error">
          {error} <button type="button" onClick={() => setReload((n) => n + 1)}>Retry</button>
        </div>
      )}
      {!data && !error && <p>Loading…</p>}
      {data && data.items.length === 0 && <p className="adm-muted">No audit records yet.</p>}
      {data && data.items.length > 0 && (
        <table className="adm-table">
          <thead>
            <tr>
              <th>When</th><th>User</th><th>Role</th><th>Intent</th><th>Model</th>
              <th title="LLM prompt + completion tokens, summed over the calls this answer made (router, synthesis, memory). Local embeddings are $0 and not token-billed.">
                Tokens
              </th>
              <th>Cost (USD)</th><th>Latency (ms)</th><th>Tool path</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((r) => (
              <tr
                key={r.id}
                tabIndex={0}
                aria-selected={r.id === selected}
                onClick={() => setSelected(r.id)}
                onKeyDown={(e) => e.key === "Enter" && setSelected(r.id)}
              >
                <td title={r.created_at}>
                  <span className="adm-when">{relativeTime(r.created_at)}</span>
                  <span className="adm-muted">{r.created_at}</span>
                </td>
                <td>{r.user_id ?? <span className="adm-muted">—</span>}</td>
                <td><span className={`adm-pill role-${r.role}`}>{r.role}</span></td>
                <td>{r.intent}</td>
                <td className="adm-model" title={r.model ?? ""}>
                  {r.model ?? <span className="adm-muted">—</span>}
                </td>
                <td className="adm-num">{r.tokens.toLocaleString()}</td>
                <td className="adm-num">${r.cost_usd.toFixed(5)}</td>
                <td className="adm-num">{Math.round(r.latency_ms).toLocaleString()}</td>
                <td className="adm-path">{r.tool_path.join(" → ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <nav className="adm-pager" aria-label="Pagination">
        <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          Prev
        </button>
        <span>
          {from}–{to} of {total}
        </span>
        <button type="button" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
          Next
        </button>
      </nav>
      {selected && <AuditDetail role={identity.role} id={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
