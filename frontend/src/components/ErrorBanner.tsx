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
      <div className="banner" role="alert" data-state="error-400">
        <p>{msg}</p>
        <button type="button" className="btn" onClick={onReselectRole}>
          Reselect role
        </button>
      </div>
    );
  }
  return (
    <div className="banner" role="alert" data-state="error-502">
      <p>Something went wrong: {msg.length > MAX_LEN ? `${msg.slice(0, MAX_LEN)}…` : msg}</p>
      <div className="row">
        <button type="button" className="btn" onClick={onRetry}>
          Retry
        </button>
        <button type="button" className="btn" onClick={copyDetails}>
          Copy details
        </button>
      </div>
    </div>
  );
}
