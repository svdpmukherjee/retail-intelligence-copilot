import { SYSTEM_ERROR } from "../copy";

interface Props {
  onRetry: () => void;
}

// Plain language only: the cause (status, detail, provider) is never rendered here.
export default function ErrorBanner({ onRetry }: Props) {
  return (
    <div className="turn bot" data-state="error">
      <div className="av" aria-hidden="true">
        R
      </div>
      <div className="body">
        <div className="plainnote err" role="alert">
          <span className="ic" aria-hidden="true">
            &#9888;
          </span>
          <span>
            {SYSTEM_ERROR}
            <br />
            <button type="button" className="retry" onClick={onRetry}>
              Try again
            </button>
          </span>
        </div>
      </div>
    </div>
  );
}
