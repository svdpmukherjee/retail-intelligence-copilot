import { FormEvent, useEffect, useState } from "react";
import { getRoles, postQuery } from "./api/client";
import MessageList, { ChatMessage } from "./components/MessageList";
import "./App.css";

const USER_ID_KEY = "ric_user_id";

function initialUserId(): string {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export default function App() {
  const [roles, setRoles] = useState<string[]>([]);
  const [role, setRole] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>(initialUserId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRoles()
      .then(setRoles)
      .catch((e) => setError(errorText(e)));
  }, []);

  const canSend = role !== "" && question.trim() !== "" && !loading;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSend) return;
    const q = question.trim();
    setQuestion("");
    setError(null);
    setLoading(true);
    setMessages((m) => [...m, { id: m.length, role: "user", text: q }]);
    try {
      const res = await postQuery({ query: q, role, thread_id: threadId, user_id: userId });
      setThreadId(res.thread_id);
      if (res.user_id) setUserId(res.user_id);
      setMessages((m) => [
        ...m,
        { id: m.length, role: "assistant", text: res.answer, citations: res.citations },
      ]);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="chat">
      <h1>Retail Intelligence Copilot</h1>
      <label className="role-picker">
        Role{" "}
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Select a role...</option>
          {roles.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <MessageList messages={messages} />
      {loading && <p className="loading">Thinking...</p>}
      <form onSubmit={onSubmit} className="composer">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={role ? "Ask a question" : "Select a role first"}
        />
        <button type="submit" disabled={!canSend}>
          Send
        </button>
      </form>
    </main>
  );
}
