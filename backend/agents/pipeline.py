import asyncio
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from agents.composer import SQL_SOURCE, AnswerResult, compose
from agents.docs_rag import docs_rag
from agents.review_rag import review_rag
from agents.router import route
from agents.sql_agent import SQLComputeError, sql_agent
from app.config import get_settings
from app.cost import CostLedger
from governance.audit import record_audit
from governance.policy import AccessDenied
from memory.manager import MemoryContext, MemoryManager, effective_query
from memory.store import get_memory_store
from observability.tracing import TraceHandle, get_tracer
from retrieval.schema import SearchHit

log = logging.getLogger(__name__)
_schema_ready = False


class PipelineError(Exception):
    """An upstream tool (router, SQL, retrieval, LLM) failed; message is safe to show."""


def ensure_memory_schema() -> None:
    """Create the memory tables once per process (the DDL is also IF NOT EXISTS)."""
    global _schema_ready
    if not _schema_ready:
        get_memory_store().ensure_schema()
        _schema_ready = True


def new_thread(user_id: str, role: str) -> str:
    ensure_memory_schema()
    return get_memory_store().create_thread(user_id, role).id


def _load_context(thread_id: str, user_id: str, role: str) -> MemoryContext:
    ensure_memory_schema()
    return MemoryManager().load(thread_id, user_id, role, limit=get_settings().memory_history_turns)


def _start_trace(role: str) -> TraceHandle | None:
    try:
        return get_tracer().start_trace("query", metadata={"role": role})
    except Exception as exc:  # tracing is best-effort: it must never fail the turn
        log.warning("trace start failed: %s", type(exc).__name__)
        return None


def _end_trace(trace: TraceHandle | None, metadata: dict) -> None:
    if trace is None:
        return
    try:
        trace.end(metadata)
    except Exception as exc:
        log.warning("trace end failed: %s", type(exc).__name__)


@contextmanager
def _stage(trace: TraceHandle | None, name: str, ledger: CostLedger) -> Iterator[None]:
    """Span one stage, recording latency and the ledger delta. Numeric metadata only, never text."""
    cm = span = None
    if trace is not None:
        try:
            cm = trace.span(name)
            span = cm.__enter__()
        except Exception as exc:
            log.warning("trace span failed: %s", type(exc).__name__)
            cm = span = None
    tokens, usd, t0 = ledger.tokens, ledger.usd, time.perf_counter()
    try:
        yield
    finally:
        if cm is not None:
            try:
                span.update(
                    {
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                        "tokens": ledger.tokens - tokens,
                        "cost_usd": ledger.usd - usd,
                    }
                )
                cm.__exit__(None, None, None)
            except Exception as exc:
                log.warning("trace span failed: %s", type(exc).__name__)


async def answer(
    query: str, role: str, *, thread_id: str | None = None, user_id: str | None = None
) -> AnswerResult:
    """router -> tool(s) -> composer under one CostLedger; returns the answer plus audit record.

    With thread_id and user_id (and memory_enabled) the turn also loads and persists memory; a
    memory failure never fails the turn, it is recorded in audit["memory"]["error"].
    """
    memory_on = bool(thread_id and user_id and get_settings().memory_enabled)
    memory: dict | None = None
    context: MemoryContext | None = None
    if memory_on:
        memory = {"thread_id": thread_id, "history_turns_used": 0, "persisted": 0}
        try:
            context = await asyncio.to_thread(_load_context, thread_id, user_id, role)
            memory["history_turns_used"] = len(context.history)
        except Exception as exc:  # memory is optional: degrade to a plain answer
            log.warning("memory load failed: %s", type(exc).__name__)
            memory["error"] = f"load: {type(exc).__name__}"
    retrieval_query = effective_query(query, context) if context else query
    if memory is not None:
        memory["followup_augmented"] = retrieval_query != query
    ctx = {"context": context} if context else {}  # no memory: M4 call shape unchanged
    started = time.perf_counter()
    ledger = CostLedger()
    tool_path: list[str] = []
    sql_result: dict | None = None
    sql_error: str | None = None
    hits: list[SearchHit] = []
    trace = _start_trace(role)
    try:
        with _stage(trace, "route", ledger):
            decision = await route(retrieval_query, role, ledger, **ctx)
        if decision.intent in ("sql", "sql_rag"):
            tool_path.append("sql_agent")
            try:
                with _stage(trace, "sql_agent", ledger):
                    sql_result = await sql_agent(query, decision.scope, ledger)
            except SQLComputeError as exc:  # degrade to whatever evidence remains, not a 502
                log.warning("sql_agent could not compute: %s", exc)
                sql_error = "could not compute"
        if decision.intent in ("review_rag", "sql_rag"):
            tool_path.append("review_rag")
            with _stage(trace, "review_rag", ledger):
                hits = await asyncio.to_thread(review_rag, retrieval_query, decision.scope)
        if decision.intent == "docs_rag":
            tool_path.append("docs_rag")
            with _stage(trace, "docs_rag", ledger):
                hits = await asyncio.to_thread(docs_rag, retrieval_query, decision.scope)
        with _stage(trace, "compose", ledger):
            result = await compose(query, sql_result, hits, ledger, **ctx)
    except PipelineError:
        raise
    except AccessDenied as exc:
        raise PipelineError(f"AccessDenied: {exc}") from exc
    except Exception as exc:  # DuckDB/DB/HTTP errors are all upstream failures to the caller
        raise PipelineError(f"{type(exc).__name__}: {exc}") from exc

    _end_trace(trace, {"intent": decision.intent, "tool_path": ",".join(tool_path)})
    result.audit.update(
        query=query,
        role=role,
        intent=decision.intent,
        tool_path=tool_path,
        sources=([SQL_SOURCE] if sql_result is not None else []) + [h.chunk.id for h in hits],
        tokens=ledger.tokens,
        cost_usd=ledger.usd,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    categories = list(decision.scope.get("category", []))
    result.audit["scope"] = {"restricted": bool(categories), "categories": categories}
    if sql_error:
        result.audit["sql_error"] = sql_error
    if memory is not None:
        if "error" not in memory:
            try:
                memory["persisted"] = await MemoryManager().persist(
                    thread_id, user_id, role, query, result, ledger, scope=decision.scope
                )
            except Exception as exc:
                log.warning("memory persist failed: %s", type(exc).__name__)
                memory["error"] = f"persist: {type(exc).__name__}"
        result.audit["memory"] = memory
        result.audit.update(tokens=ledger.tokens, cost_usd=ledger.usd)
    if get_settings().audit_enabled:
        try:
            await asyncio.to_thread(record_audit, result.audit)
        except Exception as exc:  # the audit trail is best-effort: it must never fail the turn
            log.warning("audit write failed: %s", type(exc).__name__)
    return result
