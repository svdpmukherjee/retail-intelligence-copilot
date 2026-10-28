import { TAGLINE, startersFor } from "../copy";

interface Props {
  role: string;
  onStarter: (q: string) => void;
}

export default function EmptyState({ role, onStarter }: Props) {
  return (
    <div className="empty">
      <h2>Retail Intelligence Copilot</h2>
      <p className="muted">{TAGLINE}</p>
      {role === "" ? (
        <p className="muted">Select a role to get started.</p>
      ) : (
        <ul className="chips" aria-label="Starter questions">
          {startersFor(role).map((q) => (
            <li key={q}>
              <button type="button" className="chip chip-btn" onClick={() => onStarter(q)}>
                {q}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
