import { useEffect, useRef, useState } from "react";
import type { Citation } from "../api/types";

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
  const closeRef = useRef<HTMLButtonElement>(null);

  // Opening the phone sheet moves focus in; App returns it to the chip on close.
  useEffect(() => {
    if (asSheet) closeRef.current?.focus();
  }, [asSheet]);

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
          <button ref={closeRef} type="button" className="close" onClick={onClose} aria-label="Close evidence">
            &times;
          </button>
        </div>
        {shown === null ? (
          <div className="ebody">
            <div className="eempty">Tap a Source on any answer to read the exact words it came from.</div>
          </div>
        ) : (
          <div className="ebody" aria-live="polite">
            <div className="ev-item">
              <div className="eh">
                <span className="dot" aria-hidden="true" />
                {shown.display_label}
              </div>
              {shown.snippet ? (
                <div className="esnip">&ldquo;{shown.snippet.replace(/<br\s*\/?>/gi, "\n")}&rdquo;</div>
              ) : (
                <div className="esnip nullsnip">the exact words aren&rsquo;t available to show.</div>
              )}
              {shown.passage && shown.passage !== shown.snippet && (
                <details className="full-evidence"><summary>Read full passage</summary>
                  <div className="esnip">{shown.passage}</div>
                </details>
              )}
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
