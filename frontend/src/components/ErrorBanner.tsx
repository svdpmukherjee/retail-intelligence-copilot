import { ApiError } from "../api/client";
import { errorMessage } from "../panelState";

interface Props {
  error: unknown;
  onReselectRole: () => void;
  onRetry: () => void;
}

const MAX_LEN = 240;

export default function ErrorBanner({ error, onReselectRole, onRetry }: Props) {
  const msg = errorMessage(error);
  const is400 = error instanceof ApiError && error.status === 400;

  async function copyDetails() {
    try {
      await navigator.clipboard.writeText(msg);
    } catch {
      // clipboard unavailable (insecure context): the message is still visible on screen
    }
  }

  if (is400) {
    return (
      <div className="banner e400" role="alert" data-state="error-400">
        <span className="ic" aria-hidden="true">
          &#10022;
        </span>
        <div>
          <div className="bt">Can&rsquo;t run that request.</div>
          <div className="bd">
            <code>{msg}</code>
            <br />
            Pick a valid role from the list and try again.
          </div>
          <div className="acts">
            <button type="button" onClick={onReselectRole}>
              Reselect role
            </button>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="banner e502" role="alert" data-state="error-502">
      <span className="ic" aria-hidden="true">
        &#9889;
      </span>
      <div>
        <div className="bt">The copilot had an upstream problem.</div>
        <div className="bd">
          <code>{msg.length > MAX_LEN ? `${msg.slice(0, MAX_LEN)}…` : msg}</code>
          <br />
          Your question wasn&rsquo;t changed &mdash; you can retry.
        </div>
        <div className="acts">
          <button type="button" onClick={onRetry}>
            Retry
          </button>
          <button type="button" onClick={copyDetails}>
            Copy details
          </button>
        </div>
      </div>
    </div>
  );
}
