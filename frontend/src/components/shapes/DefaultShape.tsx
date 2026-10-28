import ClaimLine from "../ClaimLine";
import type { ShapeProps } from "./types";

export default function DefaultShape({ lines, onCiteClick }: ShapeProps) {
  return (
    <div className="shape shape-default">
      {lines.map((l, i) => (
        <ClaimLine key={i} line={l} onCiteClick={onCiteClick} />
      ))}
    </div>
  );
}
