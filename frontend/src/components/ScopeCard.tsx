import type { Audit } from "../api/types";

interface Props {
  role: string;
  audit: Audit | null;
}

// Read-only. Scope facts come solely from the server's audit.scope; no category
// name is ever authored in the frontend (ADR condition).
export default function ScopeCard({ role, audit }: Props) {
  const scope = audit && audit.role === role ? audit.scope : null;
  if (!scope) {
    return (
      <div className="scope" role="group" aria-label="Access scope">
        <div className="st">Scope</div>
        <p>Shown after the first answer for this role.</p>
      </div>
    );
  }
  return (
    <div className={`scope ${scope.restricted ? "scoped" : "open-acc"}`} role="group" aria-label="Access scope">
      <div className="st">
        <span className="lk" aria-hidden="true">
          {scope.restricted ? "\u{1F512}" : "\u{1F513}"}
        </span>{" "}
        {scope.restricted ? "Filtered to your categories" : "Unrestricted"}
      </div>
      <p>
        {scope.restricted
          ? "Evidence is filtered to your role's categories at retrieval, before the model."
          : "All categories are in scope. Retrieval is not filtered for this role."}
      </p>
      {scope.categories.length > 0 && (
        <div className="cats">
          {scope.categories.map((c) => (
            <span key={c} className="ct">
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
