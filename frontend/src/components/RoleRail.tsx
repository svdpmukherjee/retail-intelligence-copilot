import type { Audit } from "../api/types";
import type { ThreadListItem } from "../api/types";
import type { Identity } from "../identities";
import BrandCard from "./BrandCard";
import HistoryRail from "./HistoryRail";
import IdentitySwitcher from "./IdentitySwitcher";
import ScopeCard from "./ScopeCard";
import SessionCard from "./SessionCard";
import ThemeToggle from "./ThemeToggle";

interface Props {
  identity: Identity;
  onIdentity: (identity: Identity) => void;
  audit: Audit | null;
  threadId: string | null;
  threads: ThreadListItem[];
  threadsError: string | null;
  onSelectThread: (id: string) => void;
  onNewChat: () => void;
  identitySelectRef: React.Ref<HTMLSelectElement>;
}

export default function RoleRail({
  identity,
  onIdentity,
  audit,
  threadId,
  threads,
  threadsError,
  onSelectThread,
  onNewChat,
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
        <ScopeCard role={identity.role} audit={audit} />
      </section>
      <HistoryRail threads={threads} error={threadsError} activeId={threadId} onSelect={onSelectThread} onNewChat={onNewChat} />
      <SessionCard audit={audit} threadId={threadId} userId={identity.userId} />
    </aside>
  );
}
