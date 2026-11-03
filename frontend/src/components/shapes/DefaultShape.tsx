import AnswerDocument from "../AnswerDocument";
import SqlData from "./SqlData";
import type { ShapeProps } from "./types";

export default function DefaultShape({ res, suppressCharts, onCiteClick }: ShapeProps) {
  return <div className="shape shape-default">
    <AnswerDocument text={res.answer} onCiteClick={onCiteClick} validCitations={res.citations.map((c) => c.n)} />
    {!suppressCharts && res.sql && <SqlData block={res.sql} />}
  </div>;
}
