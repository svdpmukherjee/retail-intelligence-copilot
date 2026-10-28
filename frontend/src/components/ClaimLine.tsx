import { parseLine } from "../answer";

interface Props {
  line: string;
  onCiteClick: (n: number) => void;
  variant?: "line" | "quote" | "t";
}

// "t" renders a span so it can sit inside a support issue/fix row.
export default function ClaimLine({ line, onCiteClick, variant = "line" }: Props) {
  const parts = parseLine(line).map((s, i) =>
    s.kind === "text" ? (
      <span key={i}>{s.text}</span>
    ) : (
      <button key={i} type="button" className="cmark" aria-label={`Show evidence ${s.n}`} onClick={() => onCiteClick(s.n)}>
        [{s.n}]
      </button>
    ),
  );
  return variant === "t" ? <span className="t">{parts}</span> : <p className={variant}>{parts}</p>;
}
