import type { Turn } from "../turns";
import AssistantTurn from "./AssistantTurn";
import UserTurn from "./UserTurn";
import { derivePanelState } from "../panelState";

interface Props {
  turns: Turn[];
  activeTurnId: string | null;
  activeN: number | null;
  onCiteClick: (turnId: string, n: number) => void;
}

// Oldest -> newest. Live turns carry their own QueryResponse (full strip and
// evidence); restored turns carry stored text only and never invent either.
export default function StackedTurns({ turns, activeTurnId, activeN, onCiteClick }: Props) {
  return (
    <>
      {turns.map((t) => {
        if (t.kind === "restored") {
          return t.roleKind === "user" ? (
            <UserTurn key={t.id} query={t.content} />
          ) : (
            <AssistantTurn key={t.id} historical={{ role: t.threadRole, content: t.content }} />
          );
        }
        return (
          <div key={t.id} className="exchange">
            <UserTurn query={t.query} />
            <AssistantTurn
              res={t.res}
              state={derivePanelState({ inFlight: false, response: t.res, error: null })}
              activeN={t.id === activeTurnId ? activeN : null}
              onCiteClick={(n) => onCiteClick(t.id, n)}
            />
          </div>
        );
      })}
    </>
  );
}
