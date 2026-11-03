import AnswerDocument from "../AnswerDocument";
import SqlData from "./SqlData";
import type { ShapeProps } from "./types";

export default function MarketingShape({ res, suppressCharts, onCiteClick }: ShapeProps) {
  return <div className="shape shape-marketing">
    <AnswerDocument text={res.answer} onCiteClick={onCiteClick} validCitations={res.citations.map((c) => c.n)} />
    {!suppressCharts && res.sql && <SqlData block={res.sql} />}
  </div>;
}
