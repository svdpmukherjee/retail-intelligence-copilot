import asyncio
import logging
import time

from agents.composer import SQL_SOURCE, AnswerResult, compose
from agents.docs_rag import docs_rag
from agents.review_rag import review_rag
from agents.router import route
from agents.sql_agent import SQLComputeError, sql_agent
from app.config import get_settings
from app.cost import CostLedger
from governance.audit import record_audit
from governance.policy import AccessDenied
from memory.manager import MemoryContext, MemoryManager
from memory.store import get_memory_store
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
    ctx = {"context": context} if context else {}  # no memory: M4 call shape unchanged
    started = time.perf_counter()
    ledger = CostLedger()
    tool_path: list[str] = []
    sql_result: dict | None = None
    sql_error: str | None = None
    hits: list[SearchHit] = []
    try:
        decision = await route(query, role, ledger, **ctx)
        if decision.intent in ("sql", "sql_rag"):
            tool_path.append("sql_agent")
            try:
                sql_result = await sql_agent(query, decision.scope, ledger)
            except SQLComputeError as exc:  # degrade to whatever evidence remains, not a 502
                log.warning("sql_agent could not compute: %s", exc)
                sql_error = "could not compute"
        if decision.intent in ("review_rag", "sql_rag"):
            tool_path.append("review_rag")
            hits = await asyncio.to_thread(review_rag, query, decision.scope)
        if decision.intent == "docs_rag":
            tool_path.append("docs_rag")
            hits = await asyncio.to_thread(docs_rag, query, decision.scope)
        result = await compose(query, sql_result, hits, ledger, **ctx)
    except PipelineError:
        raise
    except AccessDenied as exc:
        raise PipelineError(f"AccessDenied: {exc}") from exc
    except Exception as exc:  # DuckDB/DB/HTTP errors are all upstream failures to the caller
        raise PipelineError(f"{type(exc).__name__}: {exc}") from exc

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
