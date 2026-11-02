import type { ThreadListItem } from "../api/types";
import { relativeTime } from "../identities";

interface RowProps {
  thread: ThreadListItem;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

function HistoryRow({ thread, active, onSelect, onDelete }: RowProps) {
  // A row is a select button plus a sibling delete button (never nested buttons).
  return (
    <div className={`histrow-wrap${active ? " active" : ""}`}>
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
      <button
        type="button"
        className="histdel"
        title="Delete this conversation permanently"
        aria-label={`Delete conversation: ${thread.label}`}
        onClick={() => onDelete(thread.id)}
      >
        &times;
      </button>
    </div>
  );
}

interface Props {
  threads: ThreadListItem[];
  error: string | null;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
}

export default function HistoryRail({ threads, error, activeId, onSelect, onNewChat, onDelete, onDeleteAll }: Props) {
  return (
    <section className="card history" aria-label="Your conversations">
      <h2>
        Your Chat History
      </h2>
      <div className="histactions">
        <button type="button" className="newchat" onClick={onNewChat}>
          &#43; new chat
        </button>
        {threads.length > 0 && (
          <button
            type="button"
            className="histclear"
            title="Delete all conversations permanently"
            onClick={onDeleteAll}
          >
            Clear all
          </button>
        )}
      </div>
      {error && (
        <div className="histerr" role="alert">
          We couldn&rsquo;t load your conversations right now.
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
          <HistoryRow key={t.id} thread={t} active={t.id === activeId} onSelect={onSelect} onDelete={onDelete} />
        ))}
      </div>
    </section>
  );
}
