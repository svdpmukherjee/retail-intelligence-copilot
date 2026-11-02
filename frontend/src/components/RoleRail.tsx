import type { ThreadListItem } from "../api/types";
import type { Identity } from "../identities";
import BrandCard from "./BrandCard";
import HistoryRail from "./HistoryRail";
import IdentitySwitcher from "./IdentitySwitcher";
import ThemeToggle from "./ThemeToggle";

interface Props {
  identity: Identity;
  onIdentity: (identity: Identity) => void;
  threadId: string | null;
  threads: ThreadListItem[];
  threadsError: string | null;
  onSelectThread: (id: string) => void;
  onNewChat: () => void;
  onDeleteThread: (id: string) => void;
  onDeleteAll: () => void;
  identitySelectRef: React.Ref<HTMLSelectElement>;
}

export default function RoleRail({
  identity,
  onIdentity,
  threadId,
  threads,
  threadsError,
  onSelectThread,
  onNewChat,
  onDeleteThread,
  onDeleteAll,
  identitySelectRef,
}: Props) {
  return (
    <aside className="rail">
      <section className="card brandcard" aria-label="Product">
        <BrandCard />
        <ThemeToggle />
      </section>
      <section className="card ident" aria-label="Demo identity">
        <IdentitySwitcher identity={identity} onIdentity={onIdentity} selectRef={identitySelectRef} />
      </section>
      <HistoryRail
        threads={threads}
        error={threadsError}
        activeId={threadId}
        onSelect={onSelectThread}
        onNewChat={onNewChat}
        onDelete={onDeleteThread}
        onDeleteAll={onDeleteAll}
      />
    </aside>
  );
}
