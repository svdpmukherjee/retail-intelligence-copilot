import type { Audit } from "../api/types";

interface Props {
  role: string;
  audit: Audit | null;
}

// Read-only. Scope facts come solely from the server's audit.scope; no category
// name is ever authored in the frontend (ADR condition).
export default function ScopeCard({ role, audit }: Props) {
  const scope = audit && audit.role === role ? audit.scope : null;
  return (
    <section className="card" aria-label="Access scope">
      <h2>Scope</h2>
      {!scope ? (
        <p className="muted">Shown after the first answer for this role.</p>
      ) : (
        <>
          <p>{scope.restricted ? "Scoped access" : "Unrestricted access"}</p>
          {scope.categories.length > 0 && (
            <ul className="chips">
              {scope.categories.map((c) => (
                <li key={c} className="chip">
                  {c}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
