import { createElement, type ReactNode } from "react";

interface Props {
  text: string;
  onCiteClick: (n: number) => void;
  validCitations?: number[];
}

// Deliberately bounded Markdown subset. Everything becomes React text/elements;
// source HTML is never interpreted, and code spans never become citation links.
export default function AnswerDocument({ text, onCiteClick, validCitations }: Props) {
  function inline(value: string): ReactNode[] {
    const token = /`([^`]+)`|\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*]+)\*|_([^_]+)_|\[([^\]]+)\]\(([^)]+)\)/g;
    const nodes: ReactNode[] = [];
    let last = 0;
    for (const match of value.matchAll(token)) {
      const at = match.index ?? 0;
      if (at > last) nodes.push(value.slice(last, at));
      const key = `token-${at}`;
      if (match[1]) nodes.push(<code key={key}>{match[1]}</code>);
      else if (match[2]) {
        for (const n of match[2].split(",").map(Number)) {
          nodes.push(validCitations && !validCitations.includes(n) ? `[${n}]` :
            <button key={`${key}-${n}`} type="button" className="cmark" aria-label={`Show evidence ${n}`} onClick={() => onCiteClick(n)}>[{n}]</button>);
        }
      } else if (match[3] || match[4]) nodes.push(<strong key={key}>{inline(match[3] || match[4])}</strong>);
      else if (match[5] || match[6]) nodes.push(<em key={key}>{inline(match[5] || match[6])}</em>);
      else {
        // Generated links are labels only; evidence links are the numbered buttons.
        nodes.push(<span key={key}>{match[7]}</span>);
      }
      last = at + match[0].length;
    }
    if (last < value.length) nodes.push(value.slice(last));
    return nodes;
  }
  const lines = text.replace(/<br\s*\/?>/gi, "\n").split("\n");
  const blocks: ReactNode[] = [];
  const isList = (line: string) => /^\s*(?:[-*+]\s+|\d+[.)]\s+)/.test(line);
  const isHeading = (line: string) => /^#{1,6}\s+/.test(line);
  const divider = (line: string) => /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  const cells = (line: string) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
  for (let i = 0; i < lines.length;) {
    const line = lines[i].trim();
    if (!line) { i++; continue; }
    const key = `block-${i}`;
    if (/^```/.test(line)) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i].trim())) code.push(lines[i++]);
      if (i < lines.length) i++;
      blocks.push(<pre key={key}><code>{code.join("\n")}</code></pre>);
    } else if (isHeading(line)) {
      const heading = /^(#{1,6})\s+(.*)$/.exec(line)!;
      blocks.push(createElement(`h${Math.min(heading[1].length + 1, 6)}`, { key }, inline(heading[2])));
      i++;
    } else if (line.includes("|") && i+1 < lines.length && divider(lines[i+1])) {
      const headers = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) rows.push(cells(lines[i++]));
      blocks.push(<div className="markdown-table" key={key}><table><thead><tr>{headers.map((h,j) => <th scope="col" key={j}>{inline(h)}</th>)}</tr></thead>
        <tbody>{rows.map((row,j) => <tr key={j}>{headers.map((_,k) => <td key={k}>{inline(row[k] ?? "")}</td>)}</tr>)}</tbody></table></div>);
    } else if (isList(line)) {
      const ordered = /^\d/.test(line);
      const items: ReactNode[] = [];
      while (i < lines.length && isList(lines[i]) && /^\s*\d/.test(lines[i]) === ordered) {
        items.push(<li key={i}>{inline(lines[i++].replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+)/, ""))}</li>);
      }
      blocks.push(ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>);
    } else if (line.startsWith("> ")) {
      blocks.push(<blockquote key={key}>{inline(line.slice(2))}</blockquote>);
      i++;
    } else {
      const paragraph = [line]; i++;
      while (i < lines.length && lines[i].trim() && !isHeading(lines[i]) && !isList(lines[i]) &&
             !/^(?:```|> )/.test(lines[i]) && !(i+1 < lines.length && divider(lines[i+1]))) paragraph.push(lines[i++].trim());
      blocks.push(<p className="line" key={key}>{inline(paragraph.join(" "))}</p>);
    }
  }
  return <div className="answer-document">{blocks}</div>;
}
