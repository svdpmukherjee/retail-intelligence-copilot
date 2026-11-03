import json
import re
from typing import Literal, get_args

import httpx
from pydantic import BaseModel

from agents.llm import LLM, get_llm
from agents.model_policy import model_for
from agents.query_plan import constrained_scope, product_explanation
from app.cost import CostLedger
from governance.policy import scope_for_role
from memory.manager import MemoryContext
from retrieval.embeddings import GoAheadRequired
from retrieval.vector_store import Filters

Intent = Literal["sql", "review_rag", "docs_rag", "sql_rag", "clarify"]
INTENTS: tuple[str, ...] = get_args(Intent)

SYSTEM_PROMPT = (
    "Classify the user's retail question into exactly one intent: "
    "sql (counts, averages, trends, rankings over structured data); "
    "review_rag (what customers say in reviews); "
    "docs_rag (policies, warranty, returns, manuals, how-to); "
    "sql_rag (why a metric changed: needs numbers plus review evidence); "
    "clarify (the question is too vague to answer well, or asks for data that is not available "
    "— ask one short clarifying question instead of guessing). "
    "The data is customer reviews and product ratings/prices/categories — there is NO sales, "
    "revenue, profit or units-sold data. "
    'Reply with only JSON: {"intent": "<intent>", "rationale": "<short reason>", '
    '"question": "<one clarifying question, only when intent is clarify>"}.'
)

# The Gold table is review-grain (ratings, prices, categories, review counts) with no sales ledger:
# these measures have no column at all. Rather than emit SUM(<nothing>) and dump a page of nulls,
# the copilot says so and offers what it *can* answer — a conversation, not a one-way dead end.
_MISSING_MEASURE = re.compile(
    r"\b(revenue|sales|profit|margin|income|turnover|earnings|units?\s+sold|quantity\s+sold"
    r"|best[- ]?sell\w*|top[- ]?sell\w*)\b",
    re.IGNORECASE,
)
_MISSING_MEASURE_QUESTION = (
    "I don't have sales or revenue figures for these products — the data covers customer ratings, "
    "review counts and categories, not transactions. Would you like the best-rated or the "
    "most-reviewed products instead?"
)

# Order matters: "why did X drop" must win over the plain aggregate words it also contains.
_RULES: tuple[tuple[Intent, re.Pattern[str], str], ...] = (
    (
        "sql_rag",
        re.compile(
            r"\bwhy\b.*\b(chang\w*|drop\w*|increas\w*|decreas\w*|declin\w*|fell|fall|rose|rise"
            r"|spik\w*|dip\w*)\b",
            re.IGNORECASE,
        ),
        "asks why a metric changed: numbers plus review evidence",
    ),
    (
        "sql",
        re.compile(
            r"\b(how many|count|number of|average|avg|mean|median|total|sum|trend\w*|top \d+"
            r"|top[- ]?(?:rated|selling)|most[- ]?reviewed|best[- ]?rated|worst[- ]?rated"
            r"|highest[- ]?rated|lowest[- ]?rated|most[- ]?rated|bottom \d+|highest|lowest"
            r"|per month|per year)\b",
            re.IGNORECASE,
        ),
        "aggregate question over structured data",
    ),
    (
        "docs_rag",
        re.compile(
            r"\b(polic\w*|warrant\w*|returns?|refunds?|how (?:do|to|can)|manual|instructions?"
            r"|guide|setup|troubleshoot\w*)\b",
            re.IGNORECASE,
        ),
        "policy or how-to question for the documents",
    ),
)
DEFAULT_RATIONALE = "open-ended customer-voice question for the reviews"


class RouteDecision(BaseModel):
    intent: Intent
    scope: Filters
    rationale: str
    question: str | None = None  # set only when intent == "clarify": the question to ask the user
    filters: Filters | None = None  # requested constraints intersected with permission scope


def derive_scope(role: str) -> Filters:
    """Retrieval/SQL scope for `role` from the M6 access policy; raises AccessDenied if unknown.

    Callers pass it unchanged into retrieval filters (M4.2/M4.3) and the SQL agent (M4.4).
    """
    return scope_for_role(role)


def _rule_intent(query: str) -> tuple[Intent, str] | None:
    """The first matching rule, or None when the query is ambiguous."""
    if product_explanation(query):
        return "sql_rag", "select lowest-rated products, then explain with their reviews"
    for intent, pattern, why in _RULES:
        if pattern.search(query):
            return intent, why
    return None


def _parse_llm_intent(raw: str) -> tuple[Intent, str, str | None] | None:
    """(intent, rationale, question). `question` is set only for a clarify intent."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    intent = data.get("intent") if isinstance(data, dict) else None
    if intent not in INTENTS:
        return None
    rationale = str(data.get("rationale") or "LLM classification")
    if intent == "clarify":
        question = str(data.get("question") or "").strip()
        if not question:  # a clarify intent with no question is unusable: fall through to default
            return None
        return intent, rationale, question
    return intent, rationale, None


async def route(
    query: str,
    role: str,
    ledger: CostLedger | None = None,
    *,
    context: MemoryContext | None = None,
    llm: LLM | None = None,
    resolving: bool = False,
    intent_hint: Intent | None = None,
) -> RouteDecision:
    """Classify intent (rules first; LLM only for queries no rule matches) and attach the scope.

    `resolving` is set when this turn is the user's reply to a clarifying question we just asked:
    we must not clarify again (that is the loop in the transcript) — we commit to a concrete tool.
    """
    scope = derive_scope(role)
    filters = constrained_scope(query, scope)
    # Deterministic honesty gate, ahead of the aggregate rules: a question for sales/revenue data
    # the dataset does not hold is answered with a clarifying question, never a dump of nulls.
    # Skipped when resolving: the user has already been asked and has replied, so re-asking it
    # (the reply still carries the original "revenue" subject) would loop forever.
    if not resolving and _MISSING_MEASURE.search(query):
        return RouteDecision(
            intent="clarify",
            scope=scope,
            rationale="asks for sales/revenue data the review dataset does not contain",
            question=_MISSING_MEASURE_QUESTION,
        )
    if intent_hint is not None and intent_hint != "clarify":
        return RouteDecision(
            intent=intent_hint,
            scope=scope,
            filters=filters,
            rationale="server-validated conversation plan",
        )
    # Rules are high-confidence and deterministic; a nondeterministic LLM must not override them.
    if hit := _rule_intent(query):
        return RouteDecision(intent=hit[0], scope=scope, filters=filters, rationale=hit[1])
    # Classification is routed to its own tier (see model_policy); it can also decide the question
    # is too vague and return a clarify intent with a question.
    llm = llm or get_llm(model=model_for("route"))
    if llm.available:
        user = query
        if context is not None and (block := context.render()):
            user = f"{block}\n\nQuestion: {query}"
        try:
            raw = await llm.complete(
                SYSTEM_PROMPT, user, ledger=ledger or CostLedger(), max_tokens=100, task="route"
            )
        except (httpx.HTTPError, RuntimeError, GoAheadRequired):
            pass  # classification is best-effort; the default keeps the route deterministic
        else:
            if parsed := _parse_llm_intent(raw):
                # When resolving a clarification, a second clarify is not allowed: fall through to
                # the concrete default so the reply gets a real answer, not another question.
                if not (resolving and parsed[0] == "clarify"):
                    return RouteDecision(
                        intent=parsed[0],
                        scope=scope,
                        filters=filters,
                        rationale=parsed[1],
                        question=parsed[2],
                    )
    return RouteDecision(
        intent="review_rag", scope=scope, filters=filters, rationale=DEFAULT_RATIONALE
    )
