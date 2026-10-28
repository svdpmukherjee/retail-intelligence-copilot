import type { Citation } from "../api/types";

export default function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <ol className="citations">
      {citations.map((c) => (
        <li key={c.n}>
          [{c.n}] {c.label}
        </li>
      ))}
    </ol>
  );
}
