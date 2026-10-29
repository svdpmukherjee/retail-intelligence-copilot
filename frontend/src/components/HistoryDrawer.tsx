import { useEffect, useRef } from "react";
import type { ThreadListItem } from "../api/types";
import HistoryRail from "./HistoryRail";

interface Props {
  threads: ThreadListItem[];
  error: string | null;
  activeId: string | null;
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}

// Phone-only off-canvas history (CSS hides toggle + drawer above 760px). The
// identity switcher stays in the top control, not here.
export default function HistoryDrawer({ threads, error, activeId, open, onOpen, onClose, onSelect, onNewChat }: Props) {
  const toggleRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        toggleRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  function close() {
    onClose();
    toggleRef.current?.focus();
  }

  return (
    <div className="phonebar">
      <button
        ref={toggleRef}
        type="button"
        className="hist-toggle"
        aria-expanded={open}
        aria-controls="history-drawer"
        onClick={onOpen}
      >
        <span aria-hidden="true">&#9776;</span> History
      </button>
      <div className={`drawer-backdrop${open ? " on" : ""}`} onClick={close} aria-hidden="true" />
      {open && (
        <div id="history-drawer" className="history-drawer" role="dialog" aria-label="Conversation history">
          <button ref={closeRef} type="button" className="close" onClick={close} aria-label="Close history">
            &times;
          </button>
          <HistoryRail
            threads={threads}
            error={error}
            activeId={activeId}
            onSelect={(id) => {
              onSelect(id);
              close();
            }}
            onNewChat={() => {
              onNewChat();
              close();
            }}
          />
        </div>
      )}
    </div>
  );
}
