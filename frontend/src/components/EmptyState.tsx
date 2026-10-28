import { TAGLINE, startersFor } from "../copy";

interface Props {
  role: string;
  onStarter: (q: string) => void;
}

export default function EmptyState({ role, onStarter }: Props) {
  return (
    <div className="empty">
      <div className="elogo" aria-hidden="true">
        R
      </div>
      <h2>Retail Intelligence Copilot</h2>
      <div className="tagline">{TAGLINE}</div>
      {role === "" ? (
        <div className="tryh">Select a role to get started.</div>
      ) : (
        <>
          <div className="tryh">Try &mdash; for your role</div>
          <div className="starters">
            {startersFor(role).map((q) => (
              <button key={q} type="button" className="starter" onClick={() => onStarter(q)}>
                &ldquo;{q}&rdquo;
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
