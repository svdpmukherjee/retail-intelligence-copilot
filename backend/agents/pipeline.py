import asyncio
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from agents.composer import SQL_SOURCE, AnswerResult, clarification, compose
from agents.docs_rag import docs_rag
from agents.model_policy import TASKS, policy_for
from agents.review_rag import review_rag
from agents.router import route
from agents.sql_agent import SQLComputeError, sql_agent
from app.config import get_settings
from app.cost import CostLedger
from governance.audit import record_audit
from governance.pii import redact
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


def _start_trace(role: str, query: str) -> TraceHandle | None:
    try:
        # input is the operator-plane query (redacted), so the Langfuse Preview is not empty.
        return get_tracer().start_trace("query", metadata={"role": role}, input=redact(query))
    except Exception as exc:  # tracing is best-effort: it must never fail the turn
        log.warning("trace start failed: %s", type(exc).__name__)
        return None


def _record_retrieval(meta: dict, hits: list[SearchHit]) -> None:
    """Retrieval observability: how many chunks came back and how relevant the best one was.
    Scores and counts are non-PII; the chunk ids live in the audit plane (audit["sources"])."""
    meta["hits"] = len(hits)
    meta["top_score"] = round(hits[0].score, 4) if hits else 0.0
    meta["_output"] = f"{len(hits)} chunk(s) retrieved"


def _routing(ledger: CostLedger) -> list[dict]:
    """Per-task routing record for the audit plane: which model served each pipeline task, its
    capability tier, and the measured rationale for the choice (see agents.model_policy)."""
    groups: dict[str, list] = {}
    for call in ledger.llm_calls:
        groups.setdefault(call.task or "other", []).append(call)
    records = []
    for task, calls in groups.items():
        choice = policy_for(task) if task in TASKS else None
        records.append(
            {
                "task": task,
                "tier": choice.tier if choice else None,
                "rationale": choice.rationale if choice else None,
                "models": list(dict.fromkeys(c.model for c in calls)),
                "llm_calls": len(calls),
                "tokens": sum(c.total_tokens for c in calls),
                "cost_usd": round(sum(c.usd for c in calls), 6),
            }
        )
    return records


def _end_trace(trace: TraceHandle | None, metadata: dict, *, output: str | None = None) -> None:
    if trace is None:
        return
    try:
        trace.end(metadata, output=output)
    except Exception as exc:
        log.warning("trace end failed: %s", type(exc).__name__)


@contextmanager
def _stage(
    trace: TraceHandle | None, name: str, ledger: CostLedger, *, task: str | None = None
) -> Iterator[dict]:
    """Span one stage. Records its latency, ledger delta, the model(s) that served any LLM call
    made inside it and — when `task` is given — the routing tier and the rationale for that model
    (see agents.model_policy), so an operator sees not just which model ran but why. Merges the
    scalar metadata the body writes into the yielded dict; the body may also set `_input`/`_output`
    (redacted operator text) which travel on the span's input/output channel, not into metadata."""
    cm = span = None
    if trace is not None:
        try:
            cm = trace.span(name)
            span = cm.__enter__()
        except Exception as exc:
            log.warning("trace span failed: %s", type(exc).__name__)
            cm = span = None
    meta: dict = {}
    tokens, usd, calls0, t0 = ledger.tokens, ledger.usd, len(ledger.llm_calls), time.perf_counter()
    try:
        yield meta
    finally:
        if cm is not None:
            try:
                span_input = meta.pop("_input", None)
                span_output = meta.pop("_output", None)
                stage_calls = ledger.llm_calls[calls0:]
                if stage_calls:
                    meta.setdefault("model", ", ".join(dict.fromkeys(c.model for c in stage_calls)))
                    meta.setdefault("llm_calls", len(stage_calls))
                    if task is not None:
                        choice = policy_for(task)
                        meta.setdefault("tier", choice.tier)
                        meta.setdefault("model_rationale", choice.rationale)
                span.update(
                    {
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                        "tokens": ledger.tokens - tokens,
                        "cost_usd": ledger.usd - usd,
                        **meta,
                    },
                    input=span_input,
                    output=span_output,
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
    trace = _start_trace(role, query)
    try:
        with _stage(trace, "route", ledger, task="route") as meta:
            decision = await route(retrieval_query, role, ledger, **ctx)
            meta["intent"] = decision.intent
            meta["scope_restricted"] = bool(decision.scope.get("category"))
            meta["_output"] = f"{decision.intent}: {decision.rationale}"
        if decision.intent == "clarify":
            # Ask, don't guess: short-circuit the tools and return the question as the turn.
            result = clarification(
                decision.question or "Could you tell me a little more about what you're after?",
                {"grounding": {"path": "clarification", "issues": []}},
            )
        else:
            if decision.intent in ("sql", "sql_rag"):
                tool_path.append("sql_agent")
                try:
                    with _stage(trace, "sql_agent", ledger, task="sql") as meta:
                        sql_result = await sql_agent(query, decision.scope, ledger)
                        meta["rows"] = len(sql_result["rows"])
                        meta["_output"] = sql_result.get("sql")
                except SQLComputeError as exc:  # degrade to whatever evidence remains, not a 502
                    log.warning("sql_agent could not compute: %s", exc)
                    sql_error = "could not compute"
            if decision.intent in ("review_rag", "sql_rag"):
                tool_path.append("review_rag")
                with _stage(trace, "review_rag", ledger) as meta:
                    hits = await asyncio.to_thread(review_rag, retrieval_query, decision.scope)
                    _record_retrieval(meta, hits)
            if decision.intent == "docs_rag":
                tool_path.append("docs_rag")
                with _stage(trace, "docs_rag", ledger) as meta:
                    hits = await asyncio.to_thread(docs_rag, retrieval_query, decision.scope)
                    _record_retrieval(meta, hits)
            with _stage(trace, "compose", ledger, task="compose") as meta:
                result = await compose(query, sql_result, hits, ledger, **ctx)
                meta["grounding"] = result.audit.get("grounding", {}).get("path")
                meta["citations"] = len(result.citations)
                meta["_input"] = redact(query)
                meta["_output"] = redact(result.answer)
    except PipelineError:
        raise
    except AccessDenied as exc:
        raise PipelineError(f"AccessDenied: {exc}") from exc
    except Exception as exc:  # DuckDB/DB/HTTP errors are all upstream failures to the caller
        raise PipelineError(f"{type(exc).__name__}: {exc}") from exc

    # Trace-level summary: the whole-query view an operator debugging the RAG app needs — route,
    # models, grounding outcome, evidence count, and the real token/cost/latency totals.
    _end_trace(
        trace,
        {
            "intent": decision.intent,
            "tool_path": ",".join(tool_path),
            "models": ", ".join(ledger.models),
            "llm_calls": len(ledger.llm_calls),
            "grounding": result.audit.get("grounding", {}).get("path"),
            "n_sources": len(result.citations),
            "tokens": ledger.tokens,
            "cost_usd": ledger.usd,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "sql_error": bool(sql_error),
        },
        output=redact(result.answer),
    )
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
    # Traceability (set after every LLM call, incl. memory summarisation): who asked, which
    # model(s) answered, the per-call token/cost breakdown, and the answer itself — so one
    # audit row reconstructs a query -> output end to end. Operator plane only (see ux-surface).
    result.audit["user_id"] = user_id
    result.audit["answer"] = result.answer
    result.audit["model"] = ", ".join(ledger.models) or None
    result.audit["llm_calls"] = [c.as_dict() for c in ledger.llm_calls]
    # Why each model ran where: per-task tier + measured rationale (summary included, as it runs
    # during persist above). Operator plane only.
    result.audit["routing"] = _routing(ledger)
    if get_settings().audit_enabled:
        try:
            await asyncio.to_thread(record_audit, result.audit)
        except Exception as exc:  # the audit trail is best-effort: it must never fail the turn
            log.warning("audit write failed: %s", type(exc).__name__)
    return result
