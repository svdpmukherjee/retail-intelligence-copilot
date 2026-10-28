import type { Citation } from "../api/types";

interface Props {
  citations: Citation[];
  onCiteClick: (n: number) => void;
}

export default function CitationChips({ citations, onCiteClick }: Props) {
  if (citations.length === 0) return null;
  return (
    <ul className="chips" aria-label="Citations">
      {citations.map((c) => (
        <li key={c.n}>
          <button type="button" className="chip chip-btn" onClick={() => onCiteClick(c.n)}>
            [{c.n}] {c.label}
          </button>
        </li>
      ))}
    </ul>
  );
}
