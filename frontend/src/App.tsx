import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { ApiError, deleteAllThreads, deleteThread, getThread, getThreads, postQuery } from "./api/client";
import type { QueryResponse, RestoredPayload, Scope, ThreadListItem } from "./api/types";
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
import AuditView from "./admin/AuditView";
import "./App.css";

interface CenterActions {
  onCiteClick: (turnId: string, n: number) => void;
  onStarter: (q: string) => void;
  onCancel: () => void;
  onRetry: () => void;
}

function renderCenter(
  turns: Turn[],
  inFlight: boolean,
  err: unknown,
  query: string,
  role: string,
  scope: Scope | null,
  a: CenterActions,
  active: { turnId: string | null; n: number | null },
): ReactNode {
  if (turns.length === 0 && !inFlight && !err) return <EmptyState role={role} scope={scope} onStarter={a.onStarter} />;
  return (
    <>
      <StackedTurns turns={turns} activeTurnId={active.turnId} activeN={active.n} onCiteClick={a.onCiteClick} />
      {inFlight && <LoadingState query={query} onCancel={a.onCancel} />}
      {!inFlight && !!err && (
        <>
          {query && <UserTurn query={query} />}
          <ErrorBanner onRetry={a.onRetry} />
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
  // Last scope the server reported per role; never defaulted or widened client-side.
  const [scopes, setScopes] = useState<Record<string, Scope>>({});
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

  // Rebuild a full QueryResponse from a stored render snapshot so a reopened assistant turn
  // replays exactly as it drew live (charts + evidence). Operator-only audit fields the snapshot
  // omits (raw query, tokens, cost, latency) are filled with zeros; the chat never renders them.
  function restoredRes(p: RestoredPayload): QueryResponse {
    return {
      kind: p.kind ?? "answer",
      answer: p.answer,
      citations: p.citations,
      sql: p.sql,
      audit: {
        query: "",
        role: p.audit.role,
        intent: p.audit.intent,
        tool_path: p.audit.tool_path,
        sources: p.audit.sources,
        tokens: 0,
        cost_usd: 0,
        latency_ms: 0,
        grounding: p.audit.grounding,
        scope: p.audit.scope,
        ...(p.audit.sql_error ? { sql_error: p.audit.sql_error } : {}),
      },
      thread_id: null,
      user_id: null,
    };
  }

  // Restored assistant turns replay in full when a render snapshot was stored; older turns
  // without one fall back to redacted text.
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
            res: t.payload ? restoredRes(t.payload) : undefined,
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

  // Permanent history deletes. Both warn first (the data is erased from the database, not hidden).
  async function onDeleteThread(id: string) {
    const ok = window.confirm(
      "Delete this conversation permanently?\n\nIt will be erased from the database and cannot be recovered.",
    );
    if (!ok) return;
    try {
      await deleteThread(id, userId);
      if (id === threadId) resetCenter();
      void refreshThreads(identity);
    } catch (err) {
      setThreadsError(errorMessage(err));
    }
  }

  async function onDeleteAll() {
    if (threads.length === 0) return;
    const ok = window.confirm(
      `Delete all ${threads.length} conversation(s) permanently?\n\nThey will be erased from the database and cannot be recovered.`,
    );
    if (!ok) return;
    try {
      await deleteAllThreads(userId, role);
      resetCenter();
      void refreshThreads(identity);
    } catch (err) {
      setThreadsError(errorMessage(err));
    }
  }

  const latestLive = [...turns].reverse().find((t) => t.kind === "live");
  const latestRes = latestLive?.kind === "live" ? latestLive.res : null;
  const activeTurn = turns.find((t) => t.id === activeTurnId);
  // Evidence opens for live turns and for restored turns that replayed with a snapshot.
  const evidenceRes =
    activeTurn?.kind === "live" ? activeTurn.res : (activeTurn?.res ?? null);
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
  const answeringAs = latestRes ? latestRes.audit.role : role;

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
      setScopes((prev) => ({ ...prev, [role]: res.audit.scope }));
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
  };

  if (role === "admin") return <AuditView identity={identity} onIdentity={onIdentity} />;

  return (
    <div className="wrap">
      <div className="shell">
        <RoleRail
          identity={identity}
          onIdentity={onIdentity}
          threadId={threadId}
          threads={threads}
          threadsError={threadsError}
          onSelectThread={onSelectThread}
          onNewChat={resetCenter}
          onDeleteThread={onDeleteThread}
          onDeleteAll={onDeleteAll}
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
          onDeleteThread={onDeleteThread}
          onDeleteAll={onDeleteAll}
        />
        <ConversationPanel
          title="Retail Intelligence Copilot"
          answeringAs={answeringAs}
          role={role}
          question={question}
          inFlight={inFlight}
          onQuestion={setQuestion}
          onSubmit={onSubmit}
          panelState={state}
          scrollKey={turns.length + (inFlight ? 1 : 0)}
        >
          {renderCenter(turns, inFlight, currentError, lastQuery, role, scopes[role] ?? null, actions, { turnId: activeTurnId, n: activeCiteN })}
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
