import type { Audit } from "../api/types";
import BrandCard from "./BrandCard";
import ScopeCard from "./ScopeCard";
import SessionCard from "./SessionCard";
import ThemeToggle from "./ThemeToggle";

interface Props {
  roles: string[];
  role: string;
  onRole: (role: string) => void;
  audit: Audit | null;
  threadId: string | null;
  userId: string;
  roleSelectRef: React.Ref<HTMLSelectElement>;
}

export default function RoleRail({ roles, role, onRole, audit, threadId, userId, roleSelectRef }: Props) {
  return (
    <aside className="rail">
      <section className="card brandcard" aria-label="Product">
        <BrandCard />
        <ThemeToggle />
      </section>
      <section className="card" aria-label="Role">
        <label htmlFor="role-select">
          <h2>Signed in as</h2>
        </label>
        <select id="role-select" className="role" ref={roleSelectRef} value={role} onChange={(e) => onRole(e.target.value)}>
          <option value="">Select a role...</option>
          {roles.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <ScopeCard role={role} audit={audit} />
      </section>
      <SessionCard audit={audit} threadId={threadId} userId={userId} />
    </aside>
  );
}
