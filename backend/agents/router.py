import json
import re
from typing import Literal, get_args

import httpx
from pydantic import BaseModel

from agents.llm import get_llm
from app.cost import CostLedger
from governance.policy import scope_for_role
from memory.manager import MemoryContext
from retrieval.embeddings import GoAheadRequired
from retrieval.vector_store import Filters

Intent = Literal["sql", "review_rag", "docs_rag", "sql_rag"]
INTENTS: tuple[str, ...] = get_args(Intent)

SYSTEM_PROMPT = (
    "Classify the user's retail question into exactly one intent: "
    "sql (counts, averages, trends, rankings over structured data); "
    "review_rag (what customers say in reviews); "
    "docs_rag (policies, warranty, returns, manuals, how-to); "
    "sql_rag (why a metric changed: needs numbers plus review evidence). "
    'Reply with only JSON: {"intent": "<intent>", "rationale": "<short reason>"}.'
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
            r"|top[- ]?(?:rated|selling)|bottom \d+|highest|lowest|per month|per year)\b",
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


def derive_scope(role: str) -> Filters:
    """Retrieval/SQL scope for `role` from the M6 access policy; raises AccessDenied if unknown.

    Callers pass it unchanged into retrieval filters (M4.2/M4.3) and the SQL agent (M4.4).
    """
    return scope_for_role(role)


def _rule_intent(query: str) -> tuple[Intent, str] | None:
    """The first matching rule, or None when the query is ambiguous."""
    for intent, pattern, why in _RULES:
        if pattern.search(query):
            return intent, why
    return None


def _parse_llm_intent(raw: str) -> tuple[Intent, str] | None:
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
    return intent, str(data.get("rationale") or "LLM classification")


async def route(
    query: str,
    role: str,
    ledger: CostLedger | None = None,
    *,
    context: MemoryContext | None = None,
) -> RouteDecision:
    """Classify intent (rules first; LLM only for queries no rule matches) and attach the scope."""
    scope = derive_scope(role)
    # Rules are high-confidence and deterministic; a nondeterministic LLM must not override them.
    if hit := _rule_intent(query):
        return RouteDecision(intent=hit[0], scope=scope, rationale=hit[1])
    llm = get_llm()
    if llm.available:
        user = query
        if context is not None and (block := context.render()):
            user = f"{block}\n\nQuestion: {query}"
        try:
            raw = await llm.complete(
                SYSTEM_PROMPT, user, ledger=ledger or CostLedger(), max_tokens=100
            )
        except (httpx.HTTPError, RuntimeError, GoAheadRequired):
            pass  # classification is best-effort; the default keeps the route deterministic
        else:
            if parsed := _parse_llm_intent(raw):
                return RouteDecision(intent=parsed[0], scope=scope, rationale=parsed[1])
    return RouteDecision(intent="review_rag", scope=scope, rationale=DEFAULT_RATIONALE)
