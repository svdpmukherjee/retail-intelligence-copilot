import { parseLine } from "../answer";

interface Props {
  line: string;
  onCiteClick: (n: number) => void;
}

export default function ClaimLine({ line, onCiteClick }: Props) {
  return (
    <p className="claim">
      {parseLine(line).map((s, i) =>
        s.kind === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <button key={i} type="button" className="cite" aria-label={`Show evidence ${s.n}`} onClick={() => onCiteClick(s.n)}>
            [{s.n}]
          </button>
        ),
      )}
    </p>
  );
}
