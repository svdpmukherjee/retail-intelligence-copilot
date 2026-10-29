// Demo identities (D-16): not a login. user_id is the owner key; role is selected
// from it. Role -> scope stays server-side; nothing about categories lives here.
export interface Identity {
  userId: string;
  role: string;
}

export const IDENTITIES: Identity[] = [
  { userId: "support_1", role: "support" },
  { userId: "support_2", role: "support" },
  { userId: "marketing_1", role: "marketing" },
  { userId: "executive_1", role: "executive" },
];

export const DEFAULT_IDENTITY = IDENTITIES[0];

export function relativeTime(iso: string, now: number = Date.now()): string {
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(iso);
  const t = Date.parse(hasZone ? iso : `${iso.replace(" ", "T")}Z`);
  if (Number.isNaN(t)) return iso;
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
