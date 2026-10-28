import { useEffect, useRef, useState } from "react";
import type { Citation } from "../api/types";
import { evidenceType } from "../copy";

interface Props {
  citations: Citation[];
  activeN: number | null;
  open: boolean;
  onClose: () => void;
}

const SHEET_QUERY = "(max-width: 1079px)";

function useIsSheet(): boolean {
  const [sheet, setSheet] = useState(() => window.matchMedia(SHEET_QUERY).matches);
  useEffect(() => {
    const mq = window.matchMedia(SHEET_QUERY);
    const on = () => setSheet(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return sheet;
}

// Right dock on desktop, bottom sheet below 1080px (CSS keys off data-open).
export default function EvidencePanel({ citations, activeN, open, onClose }: Props) {
  const isSheet = useIsSheet();
  const closeRef = useRef<HTMLButtonElement>(null);
  const activeRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (open && isSheet) closeRef.current?.focus();
  }, [open, isSheet]);

  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [activeN, open]);

  return (
    <>
      {open && isSheet && <div className="backdrop" onClick={onClose} aria-hidden="true" />}
      <aside
        className="dock"
        aria-label="Evidence"
        data-open={open}
        onKeyDown={(e) => {
          if (e.key === "Escape" && isSheet) onClose();
        }}
      >
        <div className="dock-head">
          <h2>Evidence</h2>
          <button ref={closeRef} type="button" className="link sheet-close" onClick={onClose} aria-label="Close evidence">
            Close
          </button>
        </div>
        {citations.length === 0 ? (
          <p className="muted">Select a citation to see its source.</p>
        ) : (
          <ol className="evidence-list">
            {citations.map((c) => (
              <li
                key={c.n}
                ref={c.n === activeN ? activeRef : undefined}
                className="evidence-item"
                data-active={c.n === activeN}
              >
                <div className="row">
                  <strong>[{c.n}]</strong>
                  <span className="evidence-label">{c.label}</span>
                  <span className="tag">{evidenceType(c.source_id, c.label)}</span>
                </div>
                <div className="mono">{c.source_id}</div>
                {c.snippet && <blockquote className="snippet">{c.snippet}</blockquote>}
              </li>
            ))}
          </ol>
        )}
      </aside>
    </>
  );
}
