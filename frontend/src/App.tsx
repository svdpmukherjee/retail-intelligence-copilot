import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { ApiError, getRoles, postQuery } from "./api/client";
import type { QueryResponse } from "./api/types";
import AssistantTurn from "./components/AssistantTurn";
import ConversationPanel from "./components/ConversationPanel";
import EmptyState from "./components/EmptyState";
import ErrorBanner from "./components/ErrorBanner";
import EvidencePanel from "./components/EvidencePanel";
import LoadingState from "./components/LoadingState";
import UserTurn from "./components/UserTurn";
import RoleRail from "./components/RoleRail";
import { PanelState, derivePanelState, errorMessage } from "./panelState";
import "./App.css";

const USER_ID_KEY = "ric_user_id";
const DEFAULT_ROLE = "support";

function initialUserId(): string {
  let id = localStorage.getItem(USER_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_ID_KEY, id);
  }
  return id;
}

interface CenterActions {
  onCiteClick: (n: number) => void;
  onStarter: (q: string) => void;
  onCancel: () => void;
  onRetry: () => void;
  onReselectRole: () => void;
}

function renderCenter(
  state: PanelState,
  res: QueryResponse | null,
  err: unknown,
  query: string,
  role: string,
  a: CenterActions,
  activeN: number | null,
): ReactNode {
  switch (state) {
    case "empty":
      return <EmptyState role={role} onStarter={a.onStarter} />;
    case "loading":
      return <LoadingState query={query} onCancel={a.onCancel} />;
    case "error-400":
    case "error-502":
      return (
        <>
          {query && <UserTurn query={query} />}
          <ErrorBanner error={err} onReselectRole={a.onReselectRole} onRetry={a.onRetry} />
        </>
      );
    default:
      if (!res) return null;
      return (
        <>
          <UserTurn query={query} />
          <AssistantTurn res={res} state={state} activeN={activeN} onCiteClick={a.onCiteClick} />
        </>
      );
  }
}

export default function App() {
  const [roles, setRoles] = useState<string[]>([]);
  const [role, setRole] = useState("");
  const [question, setQuestion] = useState("");
  const [currentResponse, setCurrentResponse] = useState<QueryResponse | null>(null);
  const [currentError, setCurrentError] = useState<unknown>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [activeCiteN, setActiveCiteN] = useState<number | null>(null);
  const [inFlight, setInFlight] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string>(initialUserId);
  const [sheetOpen, setSheetOpen] = useState(false);
  const roleSelectRef = useRef<HTMLSelectElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    getRoles()
      .then((rs) => {
        setRoles(rs);
        setRole((cur) => cur || (rs.includes(DEFAULT_ROLE) ? DEFAULT_ROLE : ""));
      })
      .catch((e) => setCurrentError(e));
  }, []);

  const state = derivePanelState({ inFlight, response: currentResponse, error: currentError });
  const canSend = role !== "" && question.trim() !== "" && !inFlight;
  const meta = currentResponse ? `${currentResponse.audit.role} · ${currentResponse.audit.intent}` : role || "no role selected";

  async function send(q: string) {
    setLastQuery(q);
    setActiveCiteN(null);
    setSheetOpen(false);
    setCurrentError(null);
    setInFlight(true);
    const ctl = new AbortController();
    abortRef.current = ctl;
    try {
      const res = await postQuery({ query: q, role, thread_id: threadId, user_id: userId }, ctl.signal);
      setCurrentResponse(res);
      setThreadId(res.thread_id);
      if (res.user_id) setUserId(res.user_id);
    } catch (err) {
      setCurrentResponse(null);
      if (ctl.signal.aborted) {
        setQuestion(q);
      } else {
        setCurrentError(err instanceof ApiError ? err : new Error(errorMessage(err)));
      }
    } finally {
      setInFlight(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSend) return;
    const q = question.trim();
    setQuestion("");
    void send(q);
  }

  function onCiteClick(n: number) {
    triggerRef.current = document.activeElement as HTMLElement | null;
    setActiveCiteN(n);
    setSheetOpen(true);
  }

  function closeSheet() {
    setSheetOpen(false);
    triggerRef.current?.focus();
  }

  const actions: CenterActions = {
    onCiteClick,
    onStarter: setQuestion,
    onCancel: () => abortRef.current?.abort(),
    onRetry: () => void send(lastQuery),
    onReselectRole: () => roleSelectRef.current?.focus(),
  };

  return (
    <div className="wrap">
      <div className="shell">
        <RoleRail
          roles={roles}
          role={role}
          onRole={setRole}
          audit={currentResponse?.audit ?? null}
          threadId={threadId}
          userId={userId}
          roleSelectRef={roleSelectRef}
        />
        <ConversationPanel
          title="Retail Intelligence Copilot"
          meta={meta}
          role={role}
          question={question}
          inFlight={inFlight}
          onQuestion={setQuestion}
          onSubmit={onSubmit}
          panelState={state}
        >
          {renderCenter(state, currentResponse, currentError, lastQuery, role, actions, activeCiteN)}
        </ConversationPanel>
        <EvidencePanel
          citations={currentResponse?.citations ?? []}
          activeN={activeCiteN}
          open={sheetOpen}
          onClose={closeSheet}
        />
      </div>
    </div>
  );
}
