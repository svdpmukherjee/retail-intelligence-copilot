import { useEffect, useState } from "react";
import { getAuditRow } from "../api/client";
import type { AuditRow } from "../api/types";
import { errorMessage } from "../panelState";

interface Props {
  role: string;
  id: string;
  onClose: () => void;
}

function Json({ value }: { value: unknown }) {
  return <pre className="adm-pre">{value == null ? "none" : JSON.stringify(value, null, 2)}</pre>;
}

export default function AuditDetail({ role, id, onClose }: Props) {
  const [row, setRow] = useState<AuditRow | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setRow(null);
    setError(null);
    getAuditRow(role, id)
      .then((r) => live && setRow(r))
      .catch((err) => live && setError(errorMessage(err)));
    return () => {
      live = false;
    };
  }, [role, id]);

  return (
    <aside className="adm-detail" aria-label="Audit record">
      <button type="button" onClick={onClose}>
        Close
      </button>
      {error && <div role="alert" className="adm-error">{error}</div>}
      {!row && !error && <p>Loading…</p>}
      {row && (
        <>
          <h2>{row.query}</h2>
          <p className="adm-muted">
            #{row.id} · {row.created_at} · user {row.user_id ?? "—"} · {row.role} · {row.intent}
          </p>

          <div className="adm-metrics">
            <div className="adm-metric">
              <span className="adm-metric-k">Model</span>
              <span className="adm-metric-v">{row.model ?? "—"}</span>
            </div>
            <div className="adm-metric">
              <span className="adm-metric-k">Tokens (LLM)</span>
              <span className="adm-metric-v">{row.tokens.toLocaleString()}</span>
            </div>
            <div className="adm-metric">
              <span className="adm-metric-k">Cost</span>
              <span className="adm-metric-v">${row.cost_usd.toFixed(5)}</span>
            </div>
            <div className="adm-metric">
              <span className="adm-metric-k">Latency</span>
              <span className="adm-metric-v">{Math.round(row.latency_ms).toLocaleString()} ms</span>
            </div>
          </div>

          <h3>Answer</h3>
          <div className="adm-answer">{row.answer ?? <span className="adm-muted">not stored</span>}</div>

          <h3>LLM calls</h3>
          {row.llm_calls && row.llm_calls.length > 0 ? (
            <table className="adm-subtable">
              <thead>
                <tr><th>Model</th><th>Prompt</th><th>Completion</th><th>Total</th><th>Cost</th></tr>
              </thead>
              <tbody>
                {row.llm_calls.map((c, i) => (
                  <tr key={i}>
                    <td>{c.model}</td>
                    <td className="adm-num">{c.prompt_tokens.toLocaleString()}</td>
                    <td className="adm-num">{c.completion_tokens.toLocaleString()}</td>
                    <td className="adm-num">{c.total_tokens.toLocaleString()}</td>
                    <td className="adm-num">${c.usd.toFixed(5)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="adm-muted">No LLM call recorded (rule-routed or no provider configured).</p>
          )}

          <h3>Tool path</h3>
          <Json value={row.tool_path} />
          <h3>Sources</h3>
          <Json value={row.sources} />
          <h3>Grounding</h3>
          <Json value={row.grounding} />
          <h3>Memory</h3>
          <Json value={row.memory} />
          {row.sql_error && (
            <>
              <h3>SQL error</h3>
              <pre className="adm-pre">{row.sql_error}</pre>
            </>
          )}
        </>
      )}
    </aside>
  );
}
