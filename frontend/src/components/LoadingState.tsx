import { STAGES } from "../copy";
import UserTurn from "./UserTurn";

interface Props {
  query: string;
  onCancel: () => void;
}

// No audit or citations here: they are unknown until the response lands.
export default function LoadingState({ query, onCancel }: Props) {
  return (
    <>
      <UserTurn query={query} />
      <div className="turn" aria-busy="true">
        <p className="muted">{STAGES.join(" → ")}</p>
        <div className="skeleton" aria-hidden="true" />
        <div className="skeleton short" aria-hidden="true" />
        <button type="button" className="link" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </>
  );
}
