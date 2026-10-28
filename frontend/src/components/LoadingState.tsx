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
      <div className="turn bot" aria-busy="true">
        <div className="av" aria-hidden="true">
          R
        </div>
        <div className="body">
          <div className="load">
            <div className="stages">
              {STAGES.map((s, i) => (
                <span key={s} className={`stage${i < 2 ? " on" : ""}`}>
                  {s}
                </span>
              ))}
            </div>
            <div className="skel w1" aria-hidden="true" />
            <div className="skel w2" aria-hidden="true" />
            <div className="skel w3" aria-hidden="true" />
            <button type="button" className="cancel" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
