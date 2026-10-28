import type { Citation } from "../api/types";
import Citations from "./Citations";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
}

export default function MessageList({ messages }: { messages: ChatMessage[] }) {
  return (
    <div className="messages">
      {messages.map((m) => (
        <div key={m.id} className={`message ${m.role}`}>
          <p>{m.text}</p>
          {m.citations && <Citations citations={m.citations} />}
        </div>
      ))}
    </div>
  );
}
