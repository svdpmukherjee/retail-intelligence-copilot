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
            {row.id} · {row.created_at} · {row.role} · {row.intent}
          </p>
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
