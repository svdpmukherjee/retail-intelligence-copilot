import { TAGLINE, scopeLine, startersFor } from "../copy";
import type { Scope } from "../api/types";

interface Props {
  role: string;
  scope: Scope | null;
  onStarter: (q: string) => void;
}

export default function EmptyState({ role, scope, onStarter }: Props) {
  return (
    <div className="empty">
      <div className="elogo" aria-hidden="true">
        R
      </div>
      <h2>Ask about your reviews, products and policies</h2>
      <div className="tagline">{TAGLINE}</div>
      <div className="scopeline">{scopeLine(scope)}</div>
      {role === "" ? (
        <div className="tryh">Select a role to get started.</div>
      ) : (
        <>
          <div className="tryh">Try asking</div>
          <div className="starters">
            {startersFor(role).map((q) => (
              <button key={q} type="button" className="starter" onClick={() => onStarter(q)}>
                <span className="ar" aria-hidden="true">
                  &rarr;
                </span>
                {q}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
