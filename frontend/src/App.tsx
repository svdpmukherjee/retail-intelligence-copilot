import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { ApiError, getThread, getThreads, postQuery } from "./api/client";
import type { ThreadListItem } from "./api/types";
import type { Turn } from "./turns";
import ConversationPanel from "./components/ConversationPanel";
import EmptyState from "./components/EmptyState";
import ErrorBanner from "./components/ErrorBanner";
import EvidencePanel from "./components/EvidencePanel";
import HistoryDrawer from "./components/HistoryDrawer";
import LoadingState from "./components/LoadingState";
import StackedTurns from "./components/StackedTurns";
import UserTurn from "./components/UserTurn";
import RoleRail from "./components/RoleRail";
import { DEFAULT_IDENTITY, Identity } from "./identities";
import { PanelState, derivePanelState, errorMessage } from "./panelState";
import "./App.css";

interface CenterActions {
  onCiteClick: (turnId: string, n: number) => void;
  onStarter: (q: string) => void;
  onCancel: () => void;
  onRetry: () => void;
  onReselectRole: () => void;
}

function renderCenter(
  turns: Turn[],
  inFlight: boolean,
  err: unknown,
  query: string,
  role: string,
  a: CenterActions,
  active: { turnId: string | null; n: number | null },
): ReactNode {
  if (turns.length === 0 && !inFlight && !err) return <EmptyState role={role} onStarter={a.onStarter} />;
  return (
    <>
      <StackedTurns turns={turns} activeTurnId={active.turnId} activeN={active.n} onCiteClick={a.onCiteClick} />
      {inFlight && <LoadingState query={query} onCancel={a.onCancel} />}
      {!inFlight && !!err && (
        <>
          {query && <UserTurn query={query} />}
          <ErrorBanner error={err} onReselectRole={a.onReselectRole} onRetry={a.onRetry} />
        </>
      )}
    </>
  );
}

export default function App() {
  const [identity, setIdentity] = useState<Identity>(DEFAULT_IDENTITY);
  const { role, userId } = identity;
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [currentError, setCurrentError] = useState<unknown>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [activeCiteN, setActiveCiteN] = useState<number | null>(null);
  const [inFlight, setInFlight] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadListItem[]>([]);
  const [threadsError, setThreadsError] = useState<string | null>(null);
  const railSeq = useRef(0);
  const turnSeq = useRef(0);
  const resumeSeq = useRef(0);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [failedResumeId, setFailedResumeId] = useState<string | null>(null);
  const identitySelectRef = useRef<HTMLSelectElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function refreshThreads(id: Identity) {
    const seq = ++railSeq.current;
    try {
      const list = await getThreads(id.userId, id.role);
      if (seq !== railSeq.current) return;
      setThreads(list);
      setThreadsError(null);
    } catch (err) {
      if (seq !== railSeq.current) return;
      setThreads([]);
      setThreadsError(errorMessage(err));
    }
  }

  useEffect(() => {
    void refreshThreads(identity);
  }, [identity]);

  function resetCenter() {
    abortRef.current?.abort();
    abortRef.current = null;
    setInFlight(false);
    resumeSeq.current++;
    setTurns([]);
    setActiveTurnId(null);
    setCurrentError(null);
    setLastQuery("");
    setQuestion("");
    setActiveCiteN(null);
    setSheetOpen(false);
    setThreadId(null);
    setFailedResumeId(null);
  }

  function onIdentity(next: Identity) {
    if (next.userId === identity.userId) return;
    resetCenter();
    setThreads([]);
    setIdentity(next);
  }

  // Restored turns are stored redacted text only; audit/citations are never rebuilt.
  async function onSelectThread(id: string) {
    abortRef.current?.abort();
    abortRef.current = null;
    setInFlight(false);
    const seq = ++resumeSeq.current;
    setCurrentError(null);
    setLastQuery("");
    setActiveCiteN(null);
    setActiveTurnId(null);
    setSheetOpen(false);
    setFailedResumeId(null);
    try {
      const detail = await getThread(id, userId);
      if (seq !== resumeSeq.current) return;
      setTurns(
        [...detail.turns]
          .sort((x, y) => x.turn - y.turn)
          .map((t) => ({
            kind: "restored" as const,
            id: `${id}:${t.turn}`,
            roleKind: t.role_kind,
            content: t.content,
            threadRole: detail.role,
          })),
      );
      setThreadId(id);
    } catch (err) {
      if (seq !== resumeSeq.current) return;
      // The user left the open thread, so showing its turns under a resume error
      // would mislead; clear the stack and offer Retry on the resume itself.
      setTurns([]);
      setThreadId(null);
      setFailedResumeId(id);
      setCurrentError(err instanceof ApiError ? err : new Error(errorMessage(err)));
    }
  }

  const latestLive = [...turns].reverse().find((t) => t.kind === "live");
  const latestRes = latestLive?.kind === "live" ? latestLive.res : null;
  const activeTurn = turns.find((t) => t.id === activeTurnId);
  const evidenceRes = activeTurn?.kind === "live" ? activeTurn.res : null;
  const state = inFlight
    ? "loading"
    : currentError
      ? derivePanelState({ inFlight, response: null, error: currentError })
      : turns.length === 0
        ? "empty"
        : latestRes && turns[turns.length - 1].kind === "live"
          ? derivePanelState({ inFlight, response: latestRes, error: null })
          : "restored";
  const canSend = role !== "" && question.trim() !== "" && !inFlight;
  const meta = latestRes ? `${latestRes.audit.role} · ${latestRes.audit.intent}` : role || "no role selected";

  async function send(q: string) {
    setLastQuery(q);
    setFailedResumeId(null);
    setActiveCiteN(null);
    setSheetOpen(false);
    setCurrentError(null);
    setInFlight(true);
    resumeSeq.current++;
    const ctl = new AbortController();
    abortRef.current = ctl;
    try {
      const res = await postQuery({ query: q, role, thread_id: threadId, user_id: userId }, ctl.signal);
      const id = `live:${++turnSeq.current}`;
      setTurns((prev) => [...prev, { kind: "live", id, query: q, res }]);
      setActiveTurnId(null);
      setThreadId(res.thread_id);
      void refreshThreads(identity);
    } catch (err) {
      if (abortRef.current !== ctl) return;
      if (ctl.signal.aborted) {
        setQuestion(q);
      } else {
        setCurrentError(err instanceof ApiError ? err : new Error(errorMessage(err)));
      }
    } finally {
      if (abortRef.current === ctl) setInFlight(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSend) return;
    const q = question.trim();
    setQuestion("");
    void send(q);
  }

  function onCiteClick(turnId: string, n: number) {
    triggerRef.current = document.activeElement as HTMLElement | null;
    setActiveTurnId(turnId);
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
    onRetry: () => (failedResumeId ? void onSelectThread(failedResumeId) : lastQuery && void send(lastQuery)),
    onReselectRole: () => identitySelectRef.current?.focus(),
  };

  return (
    <div className="wrap">
      <div className="shell">
        <RoleRail
          identity={identity}
          onIdentity={onIdentity}
          audit={latestRes?.audit ?? null}
          threadId={threadId}
          threads={threads}
          threadsError={threadsError}
          onSelectThread={onSelectThread}
          onNewChat={resetCenter}
          identitySelectRef={identitySelectRef}
        />
        <HistoryDrawer
          threads={threads}
          error={threadsError}
          activeId={threadId}
          open={drawerOpen}
          onOpen={() => setDrawerOpen(true)}
          onClose={() => setDrawerOpen(false)}
          onSelect={onSelectThread}
          onNewChat={resetCenter}
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
          scrollKey={turns.length + (inFlight ? 1 : 0)}
        >
          {renderCenter(turns, inFlight, currentError, lastQuery, role, actions, { turnId: activeTurnId, n: activeCiteN })}
        </ConversationPanel>
        <EvidencePanel
          citations={evidenceRes?.citations ?? []}
          activeN={activeCiteN}
          open={sheetOpen}
          onClose={closeSheet}
        />
      </div>
    </div>
  );
}
