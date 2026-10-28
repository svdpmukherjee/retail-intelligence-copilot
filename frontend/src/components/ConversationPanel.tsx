import { FormEvent, ReactNode } from "react";

interface Props {
  title: string;
  meta: string;
  role: string;
  question: string;
  inFlight: boolean;
  onQuestion: (q: string) => void;
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
  panelState: string;
}

export default function ConversationPanel({ title, meta, role, question, inFlight, onQuestion, onSubmit, children, panelState }: Props) {
  const canSend = role !== "" && question.trim() !== "" && !inFlight;
  return (
    <main className="center" data-panel-state={panelState}>
      <header className="conv-head">
        <h1>{title}</h1>
        <p className="muted">{meta}</p>
      </header>
      <div className="stream" aria-live="polite">
        {children}
      </div>
      <form onSubmit={onSubmit} className="composer">
        <input
          value={question}
          onChange={(e) => onQuestion(e.target.value)}
          placeholder={role ? "Ask a question" : "Select a role first"}
          aria-label="Question"
          disabled={inFlight}
        />
        <button type="submit" className="btn" disabled={!canSend}>
          Send
        </button>
      </form>
    </main>
  );
}
