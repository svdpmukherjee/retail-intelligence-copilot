import AnswerDocument from "../AnswerDocument";
import SqlData from "./SqlData";
import type { ShapeProps } from "./types";

export default function SupportShape({ res, suppressCharts, onCiteClick }: ShapeProps) {
  return <div className="shape shape-support">
    <AnswerDocument text={res.answer} onCiteClick={onCiteClick} validCitations={res.citations.map((c) => c.n)} />
    {!suppressCharts && res.sql && <SqlData block={res.sql} />}
  </div>;
}
