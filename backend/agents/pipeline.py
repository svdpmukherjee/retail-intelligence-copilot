import asyncio
import logging
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager

from agents.composer import SQL_SOURCE, AnswerResult, clarification, compose, synthesize_answers
from agents.conversation import (
    PlannedQuestion,
    access_message,
    direct_action,
    restricted_categories,
    understand,
)
from agents.docs_rag import docs_rag
from agents.model_policy import TASKS, policy_for
from agents.query_plan import product_explanation, requested_categories
from agents.review_rag import review_rag
from agents.router import _rule_intent, derive_scope, route
from agents.sql_agent import SQLComputeError, sql_agent
from agents.suggestions import render_suggestions
from app.config import get_settings
from app.cost import CostLedger
from governance.audit import record_audit
from governance.pii import redact
from governance.policy import AccessDenied
from memory.manager import MemoryContext, MemoryManager
from memory.store import get_memory_store
from observability.tracing import TraceHandle, get_tracer
from retrieval.schema import SearchHit
from retrieval.source_reviews import enrich_indexed_reviews, selected_source_reviews

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
    Scores and counts are non-PII; the chunk ids live in the audit plane (audit["sources"]).
    """
    meta["hits"] = len(hits)
    meta["top_score"] = round(hits[0].score, 4) if hits else 0.0
    meta["_output"] = f"{len(hits)} chunk(s) retrieved"


def _routing(ledger: CostLedger) -> list[dict]:
    """Per-task routing record for the audit plane: which model served each pipeline task, its
    capability tier, and the measured rationale for the choice (see agents.model_policy).
    """
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
    (redacted operator text) which travel on the span's input/output channel, not into metadata.
    """
    cm = span = None
    if trace is not None:
        try:
            cm = trace.span(name)
            span = cm.__enter__()
        except Exception as exc:
            log.warning("trace span failed: %s", type(exc).__name__)
            cm = span = None
    meta: dict = {}
    tokens, usd, calls0, t0 = (
        ledger.tokens,
        ledger.usd,
        len(ledger.llm_calls),
        time.perf_counter(),
    )
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


def _conversation_reply(action: str, role: str) -> AnswerResult:
    if action == "greeting":
        message = (
            "Hello! I'm your Retail Intelligence Copilot. I can help you explore "
            "customer reviews, product ratings, recorded prices and return policies. "
            + access_message(role)
        )
    elif action == "cancel":
        message = "Okay, I’ve dropped that request. What would you like to explore next?"
    elif action == "access":
        message = access_message(role)
    else:
        message = (
            "That request is outside this copilot's scope. I can help with retail customer "
            "reviews, product ratings and policy documents."
        )
    return AnswerResult(
        answer=message,
        citations=[],
        audit={
            "intent": "conversation",
            "tool_path": [],
            "sources": [],
            "grounding": {"path": "conversation", "issues": []},
        },
    )


async def _execute_question(
    query: str,
    role: str,
    ledger: CostLedger,
    *,
    context: MemoryContext | None = None,
    resolving: bool = False,
    planned: PlannedQuestion | None = None,
    synthesize: bool = True,
) -> AnswerResult:
    """Execute one independently scoped question without persisting a chat turn."""
    action = direct_action(query)
    if action:
        return _conversation_reply(action, role)
    blocked = restricted_categories(query, role)
    rule = _rule_intent(query)
    is_policy = (planned and planned.intent == "docs_rag") or (rule and rule[0] == "docs_rag")
    allowed_requested = set(requested_categories(query)) - set(blocked)
    if blocked and not allowed_requested and not is_policy:
        labels = ", ".join(c.replace("_", " ") for c in blocked)
        result = _conversation_reply("access", role)
        result.answer = (
            f"Your {role} role doesn't have access to {labels} reviews or product data. "
            + result.answer
        )
        result.audit.update(query_filters={"category": []}, sql_outcome="empty")
        return result
    retrieval_query = query
    ctx = {"context": context} if context else {}  # no memory: M4 call shape unchanged
    started = time.perf_counter()
    tool_path: list[str] = []
    sql_result: dict | None = None
    sql_error: str | None = None
    sql_outcome: str | None = None
    hits: list[SearchHit] = []
    evidence_assessment: dict | None = None
    trace = _start_trace(role, query)
    try:
        with _stage(trace, "route", ledger, task="route") as meta:
            hint = {"intent_hint": planned.intent} if planned and planned.intent else {}
            decision = await route(
                retrieval_query, role, ledger, resolving=resolving, **ctx, **hint
            )
            meta["intent"] = decision.intent
            meta["scope_restricted"] = bool(decision.scope.get("category"))
            meta["_output"] = f"{decision.intent}: {decision.rationale}"
        tool_scope = decision.filters if decision.filters is not None else decision.scope
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
                        # retrieval_query, not query: a follow-up reply ("most-reviewed products")
                        # carries no subject on its own — text-to-SQL needs the resolved question.
                        selection_kwargs = (
                            {"selection": planned.selection}
                            if planned and planned.selection
                            else {}
                        )
                        if planned and planned.product_query:
                            selection_kwargs["product_query"] = planned.product_query
                        sql_result = await sql_agent(
                            retrieval_query, tool_scope, ledger, **selection_kwargs
                        )
                        sql_outcome = sql_result.get("status") or (
                            "success" if sql_result["rows"] else "empty"
                        )
                        meta["rows"] = len(sql_result["rows"])
                        meta["_output"] = sql_result.get("sql")
                except SQLComputeError as exc:  # degrade to whatever evidence remains, not a 502
                    log.warning("sql_agent could not compute: %s", exc)
                    sql_error = "could not compute"
                    sql_outcome = "failure"
            if decision.intent in ("review_rag", "sql_rag"):
                review_scope = dict(tool_scope)
                if product_explanation(retrieval_query) or (planned and planned.selection):
                    # No selection means no explanation evidence. Never substitute other products.
                    ids = []
                    if sql_result and "asin" in sql_result["columns"]:
                        at = sql_result["columns"].index("asin")
                        ids = [r[at] for r in sql_result["rows"] if r[at]]
                    if sql_result and sql_result["rows"] and not ids:
                        sql_error, sql_outcome = (
                            "missing product identifiers",
                            "failure",
                        )
                        sql_result = None
                    review_scope["asin"] = sorted(set(ids))
                else:
                    ids = None
                if ids is None or ids:
                    tool_path.append("review_rag")
                    with _stage(trace, "review_rag", ledger) as meta:
                        settings = get_settings()
                        source_enabled = (
                            settings.source_review_fallback and not settings.evidence_bundle_path
                        )
                        source_hits = None
                        if (
                            source_enabled
                            and ids
                            and sql_result
                            and sql_result.get("minimum_review_count")
                        ):
                            source_hits = await asyncio.to_thread(
                                selected_source_reviews, sql_result, review_scope, settings
                            )
                        if source_hits is not None:
                            # SQL already identifies the products: use their verified source
                            # reviews directly, without needing another embedding/index run.
                            hits = source_hits
                        else:
                            hits = await asyncio.to_thread(
                                review_rag, retrieval_query, review_scope
                            )
                            if source_enabled and hits:
                                hits = await asyncio.to_thread(
                                    enrich_indexed_reviews, hits, review_scope, settings
                                )
                                negative = bool(
                                    re.search(
                                        r"\b(?:complain\w*|dislike\w*|drawbacks?|downsides?|unhappy|disappoint\w*)\b",
                                        retrieval_query,
                                        re.I,
                                    )
                                )
                                positive = (
                                    bool(
                                        re.search(
                                            r"\b(?:prais\w*|positive|love|like|appreciate)\b",
                                            retrieval_query,
                                            re.I,
                                        )
                                    )
                                    and not negative
                                )
                                if negative or positive:
                                    hits = [
                                        h
                                        for h in hits
                                        if h.chunk.rating is not None
                                        and (
                                            h.chunk.rating <= 2 if negative else h.chunk.rating >= 4
                                        )
                                    ]
                        evidence_assessment = getattr(hits, "assessment", None)
                        if source_hits is not None and not source_hits and not hits:
                            evidence_assessment = source_hits.assessment
                        _record_retrieval(meta, hits)
            if decision.intent == "docs_rag":
                tool_path.append("docs_rag")
                with _stage(trace, "docs_rag", ledger) as meta:
                    hits = await asyncio.to_thread(docs_rag, retrieval_query, tool_scope)
                    evidence_assessment = getattr(hits, "assessment", None)
                    _record_retrieval(meta, hits)
            with _stage(trace, "compose", ledger, task="compose") as meta:
                # Answer the resolved question so a follow-up reply reads coherently, not as if the
                # bare "most-reviewed products" were the whole ask.
                result = await compose(
                    retrieval_query, sql_result, hits, ledger, synthesize=synthesize, **ctx
                )
                if blocked and not is_policy:
                    labels = ", ".join(c.replace("_", " ") for c in blocked)
                    result.answer = (
                        f"Your {role} role doesn't have access to {labels}; "
                        "this answer covers only permitted categories.\n\n" + result.answer
                    )
                if evidence_assessment and evidence_assessment.get("status") == "partial":
                    result.answer += (
                        "\n\nI found supporting reviews for only some " "of the selected products."
                    )
                if sql_error and not hits:
                    result.answer = "I couldn't calculate the requested results. Please try again."
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
        sources=([SQL_SOURCE] if sql_result and sql_result["rows"] else [])
        + [h.chunk.id for h in hits],
        tokens=ledger.tokens,
        cost_usd=ledger.usd,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    categories = list(decision.scope.get("category", []))
    result.audit["scope"] = {"restricted": bool(categories), "categories": categories}
    result.audit["query_filters"] = tool_scope
    if blocked and not is_policy:
        result.audit["access_notice"] = (
            f"Your {role} role doesn't have access to "
            + ", ".join(c.replace("_", " ") for c in blocked)
            + "; this answer covers only permitted categories."
        )
    if evidence_assessment:
        result.audit["evidence"] = evidence_assessment
    if sql_outcome:
        result.audit["sql_outcome"] = sql_outcome
    if sql_error:
        result.audit["sql_error"] = sql_error
    return result


def _combine_answers(results: list[AnswerResult]) -> AnswerResult:
    """Keep each part's evidence and remap references without another model call."""
    from governance.grounding import CITE

    citations, sections = [], []
    for index, result in enumerate(results, 1):
        mapping = {}
        for cite in result.citations:
            mapping[cite.n] = len(citations) + 1
            citations.append(cite.model_copy(update={"n": mapping[cite.n]}))

        def renumber(match: re.Match[str], mapping: dict[int, int] = mapping) -> str:
            numbers = [int(n.strip()) for n in match[1].split(",")]
            return "[" + ", ".join(str(mapping[n]) for n in numbers if n in mapping) + "]"

        sections.append(f"### Question {index}\n\n" + CITE.sub(renumber, result.answer))
    blocks = [r.sql for r in results if r.sql is not None]
    scope = results[0].audit.get("scope", {})
    return AnswerResult(
        answer="\n\n".join(sections),
        citations=citations,
        sql=blocks[0] if len(blocks) == 1 else None,
        audit={
            "intent": "compound",
            "scope": scope,
            "tool_path": [tool for r in results for tool in r.audit.get("tool_path", [])],
            "sources": [c.source_id for c in citations],
            "grounding": {
                "path": "composite",
                "issues": [
                    issue
                    for r in results
                    for issue in r.audit.get("grounding", {}).get("issues", [])
                ],
            },
            "parts": [r.audit for r in results],
        },
    )


async def _answer(
    query: str, role: str, *, thread_id: str | None = None, user_id: str | None = None
) -> AnswerResult:
    """router -> tool(s) -> composer under one CostLedger; returns the answer plus audit record.

    With thread_id and user_id (and memory_enabled) the turn also loads and persists memory; a
    memory failure never fails the turn, it is recorded in audit["memory"]["error"].
    """
    try:
        scope = derive_scope(role)
    except AccessDenied as exc:
        raise PipelineError(f"AccessDenied: {exc}") from exc
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
    started = time.perf_counter()
    ledger = CostLedger()
    plan = await understand(query, role, context, ledger)
    if memory is not None:
        memory["followup_augmented"] = any(p.query != query for p in plan.parts)
    if plan.action == "clarify":
        result = clarification(
            plan.message,
            {
                "intent": "clarify",
                "tool_path": [],
                "sources": [],
                "grounding": {"path": "clarification", "issues": []},
            },
        )
        result.suggestions = plan.choices
        result.clarification_state = plan.state.model_dump() if plan.state else None
    elif plan.action != "execute":
        result = _conversation_reply(plan.action, role)
    else:
        results = []
        for part in plan.parts:
            try:
                results.append(
                    await _execute_question(
                        part.query,
                        role,
                        ledger,
                        context=context if len(plan.parts) == 1 else None,
                        planned=part,
                        synthesize=len(plan.parts) == 1,
                    )
                )
            except PipelineError:
                if len(plan.parts) == 1:
                    raise
                log.warning("combined question part could not be answered")
                results.append(
                    AnswerResult(
                        answer=(
                            "I couldn't answer this part right now. "
                            "Please try this question again."
                        ),
                        citations=[],
                        audit={
                            "intent": "clarify",
                            "tool_path": [],
                            "sources": [],
                            "grounding": {"path": "none", "issues": ["tool failure"]},
                        },
                    )
                )
        if len(results) > 1:
            results = await synthesize_answers(results, [p.query for p in plan.parts], ledger)
        for part_result in results:
            if part_result.audit.get("evidence", {}).get("status") == "partial":
                limitation = "I found supporting reviews for only some of the selected products."
                if limitation not in part_result.answer:
                    part_result.answer += "\n\n" + limitation
            notice = part_result.audit.get("access_notice")
            if notice and notice not in part_result.answer:
                part_result.answer = notice + "\n\n" + part_result.answer
        result = results[0] if len(results) == 1 else _combine_answers(results)
    if plan.parts:
        result.conversation_state = {"parts": [p.model_dump() for p in plan.parts]}
    elif plan.state:
        result.conversation_state = {"parts": [p.model_dump() for p in plan.state.parts]}
    elif result.kind == "clarification" and context:
        result.conversation_state = context.conversation_state
    if result.kind != "clarification":
        actions = result.audit.get("grounding", {}).pop("suggested_actions", None)
        if result.audit.get("parts"):
            actions = [
                a
                for p in result.audit["parts"]
                for a in p.get("grounding", {}).pop("suggested_actions", [])
            ]
        result.suggestions = render_suggestions(
            role,
            " ".join(p.query for p in plan.parts) or query,
            actions,
            parts=[p.model_dump() for p in plan.parts],
            result=result.model_dump(),
        )
    result.audit.update(
        query=query,
        role=role,
        scope={
            "restricted": bool(scope.get("category")),
            "categories": list(scope.get("category", [])),
        },
        tokens=ledger.tokens,
        cost_usd=ledger.usd,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    if memory is not None:
        if "error" not in memory:
            try:
                memory["persisted"] = await MemoryManager().persist(
                    thread_id,
                    user_id,
                    role,
                    query,
                    result,
                    ledger,
                    scope=scope,
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


async def answer(
    query: str, role: str, *, thread_id: str | None = None, user_id: str | None = None
) -> AnswerResult:
    """Pin one optional evidence bundle for every tool in this turn."""
    path = get_settings().evidence_bundle_path
    if not path:
        return await _answer(query, role, thread_id=thread_id, user_id=user_id)
    from retrieval.evidence_bundle import pin_bundle

    try:
        with pin_bundle(path):
            return await _answer(query, role, thread_id=thread_id, user_id=user_id)
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"{type(exc).__name__}: evidence version could not be used") from exc
