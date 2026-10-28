import type { Citation } from "../api/types";

interface Props {
  citations: Citation[];
  activeN: number | null;
  onCiteClick: (n: number) => void;
}

export default function CitationChips({ citations, activeN, onCiteClick }: Props) {
  if (citations.length === 0) return null;
  return (
    <div className="evrow" role="group" aria-label="Citations">
      <span className="lbl">Evidence — click to inspect</span>
      {citations.map((c) => (
        <button
          key={c.n}
          type="button"
          className={`chip-cite${c.n === activeN ? " active" : ""}`}
          onClick={() => onCiteClick(c.n)}
        >
          <span className="n">[{c.n}]</span>
          <span className="cl">{c.label}</span>
        </button>
      ))}
    </div>
  );
}
