import { useEffect, useState } from "react";
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
  const asSheet = open && isSheet;
  // Exactly one citation at a time; a new [n] replaces it in place.
  const shown = citations.find((c) => c.n === activeN) ?? null;

  // No focus trap and no focus move: focus stays on the clicked [n] marker, so
  // Escape is listened for on the document while the sheet is open.
  useEffect(() => {
    if (!asSheet) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [asSheet, onClose]);

  return (
    <>
      <div className={`sheet-backdrop${asSheet ? " on" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`card evidence-dock${asSheet ? " sheet" : ""}`} aria-label="Evidence">
        <div className="ehead">
          <span className="et">Evidence</span>
          <button type="button" className="close" onClick={onClose} aria-label="Close evidence">
            &times;
          </button>
        </div>
        {shown === null ? (
          <div className="ebody">
            <div className="eempty">
              Click a citation chip or a <code style={{ fontFamily: "var(--mono)" }}>[n]</code> marker in an answer &mdash; the
              evidence it rests on appears here.
            </div>
          </div>
        ) : (
          <div className="ebody" aria-live="polite">
            <div className="ev-item active">
              <div className="eh">
                <span className="n">[{shown.n}]</span>
                <span className="el">{shown.label}</span>
                <span className="etag">{evidenceType(shown.source_id, shown.label)}</span>
              </div>
              <div className="eid">source_id: {shown.source_id}</div>
              <div className="esnip">
                {shown.snippet ? <>&ldquo;{shown.snippet}&rdquo;</> : <em>snippet unavailable</em>}
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
