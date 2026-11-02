import { LOADING } from "../copy";
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
      <div className="turn bot" aria-busy="true">
        <div className="av" aria-hidden="true">
          R
        </div>
        <div className="body">
          <div className="loading">
            <span className="spin" aria-hidden="true" />
            {LOADING}
            <button type="button" className="cancel" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
