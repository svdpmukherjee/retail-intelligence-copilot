import type { ThreadListItem } from "../api/types";
import { relativeTime } from "../identities";

interface RowProps {
  thread: ThreadListItem;
  active: boolean;
  onSelect: (id: string) => void;
}

function HistoryRow({ thread, active, onSelect }: RowProps) {
  return (
    <button
      type="button"
      className={`histrow${active ? " active" : ""}`}
      aria-current={active ? "true" : undefined}
      onClick={() => onSelect(thread.id)}
    >
      <span className="mk" aria-hidden="true"></span>
      <span className="hb">
        <span className="hl" title={thread.label}>
          {thread.label}
        </span>
        <span className="ht">{relativeTime(thread.created_at)}</span>
      </span>
    </button>
  );
}

interface Props {
  threads: ThreadListItem[];
  error: string | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}

export default function HistoryRail({ threads, error, activeId, onSelect, onNewChat }: Props) {
  return (
    <section className="card history" aria-label="Your conversations">
      <h2>
        History <span className="yours">(yours)</span>
      </h2>
      <button type="button" className="newchat" onClick={onNewChat}>
        &#43; new chat
      </button>
      {error && (
        <div className="histerr" role="alert">
          Could not load conversations: {error}
        </div>
      )}
      <div className="histlist">
        {!error && threads.length === 0 && (
          <div className="histempty">
            <b>No conversations yet.</b>
            <br />
            Start one with &ldquo;+ new chat&rdquo; above.
          </div>
        )}
        {threads.map((t) => (
          <HistoryRow key={t.id} thread={t} active={t.id === activeId} onSelect={onSelect} />
        ))}
      </div>
    </section>
  );
}
