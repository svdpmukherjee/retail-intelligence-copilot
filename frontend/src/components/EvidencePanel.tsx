import { useEffect, useRef, useState } from "react";
import type { Citation } from "../api/types";
import { evidenceType } from "../copy";

interface Props {
  citations: Citation[];
  activeN: number | null;
  open: boolean;
  onClose: () => void;
}

const SHEET_QUERY = "(max-width: 1080px)";

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

// Right dock on desktop, bottom sheet at <=1080px (CSS keys off the .sheet class).
export default function EvidencePanel({ citations, activeN, open, onClose }: Props) {
  const isSheet = useIsSheet();
  const closeRef = useRef<HTMLButtonElement>(null);
  const activeRef = useRef<HTMLLIElement>(null);
  const asSheet = open && isSheet;

  useEffect(() => {
    if (asSheet) closeRef.current?.focus();
  }, [asSheet]);

  useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [activeN, open]);

  return (
    <>
      <div className={`sheet-backdrop${asSheet ? " on" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside
        className={`card evidence-dock${asSheet ? " sheet" : ""}`}
        aria-label="Evidence"
        onKeyDown={(e) => {
          if (e.key === "Escape" && isSheet) onClose();
        }}
      >
        <div className="ehead">
          <span className="et">Evidence</span>
          <button ref={closeRef} type="button" className="close" onClick={onClose} aria-label="Close evidence">
            &times;
          </button>
        </div>
        {citations.length === 0 ? (
          <div className="ebody">
            <div className="eempty">
              Click a citation chip or a <code style={{ fontFamily: "var(--mono)" }}>[n]</code> marker in an answer &mdash; the
              evidence it rests on appears here.
            </div>
          </div>
        ) : (
          <ol className="ebody">
            {citations.map((c) => (
              <li
                key={c.n}
                ref={c.n === activeN ? activeRef : undefined}
                className={`ev-item${c.n === activeN ? " active" : ""}`}
              >
                <div className="eh">
                  <span className="n">[{c.n}]</span>
                  <span className="el">{c.label}</span>
                  <span className="etag">{evidenceType(c.source_id, c.label)}</span>
                </div>
                <div className="eid">source_id: {c.source_id}</div>
                {c.snippet && <div className="esnip">&ldquo;{c.snippet}&rdquo;</div>}
              </li>
            ))}
          </ol>
        )}
      </aside>
    </>
  );
}
