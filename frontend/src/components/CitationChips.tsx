import type { Citation } from "../api/types";

interface Props {
  citations: Citation[];
  activeN: number | null;
  onCiteClick: (n: number) => void;
}

// `n` only keys the active source; the user sees the plain-language display_label.
export default function CitationChips({ citations, activeN, onCiteClick }: Props) {
  if (citations.length === 0) return null;
  return (
    <div className="evrow" role="group" aria-label="Where this came from">
      <span className="lbl">Where this came from</span>
      {citations.map((c) => {
        const active = c.n === activeN;
        return (
          <button
            key={c.n}
            type="button"
            className={`chip-cite${active ? " active" : ""}`}
            aria-pressed={active}
            onClick={() => onCiteClick(c.n)}
          >
            <span className="dot" aria-hidden="true" />
            <span className="cl">Source: {c.display_label}</span>
            {active && <span className="viewing">viewing</span>}
          </button>
        );
      })}
    </div>
  );
}
