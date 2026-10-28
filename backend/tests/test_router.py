import asyncio

import pytest

from agents import router as mod
from agents.router import INTENTS, derive_scope, route
from retrieval.vector_store import build_where


class NoLLM:
    available = False


class FakeLLM:
    available = True

    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def complete(self, system, user, *, ledger, max_tokens=None):
        return self.reply


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr(mod, "get_llm", lambda: NoLLM())


@pytest.mark.parametrize(
    ("query", "intent"),
    [
        ("How many reviews did the blender get last month?", "sql"),
        ("What is the average rating per category?", "sql"),
        ("Top 5 products by review count", "sql"),
        ("What is the return policy for opened items?", "docs_rag"),
        ("How do I reset the coffee maker? See the manual", "docs_rag"),
        ("Why did the vacuum rating drop in March?", "sql_rag"),
        ("Why did complaints about battery life increase?", "sql_rag"),
        ("What do customers say about the headphones' comfort?", "review_rag"),
    ],
)
def test_rules_route_to_each_intent(no_llm, query, intent):
    decision = asyncio.run(route(query, "analyst"))
    assert decision.intent == intent
    assert decision.rationale


def test_all_four_intents_are_reachable(no_llm):
    queries = ["how many orders", "refund policy", "why did sales drop", "love the fit"]
    got = {asyncio.run(route(q, "analyst")).intent for q in queries}
    assert got == set(INTENTS)


def test_scope_is_open_and_passes_through_to_filters(no_llm):
    decision = asyncio.run(route("anything", "analyst"))
    assert decision.scope == derive_scope("analyst") == {}
    where, params = build_where({**decision.scope, "source_type": "review"})
    assert params == ["review"]
    assert "source_type" in where


def test_llm_decides_an_ambiguous_query(monkeypatch):
    reply = 'Sure: {"intent": "docs_rag", "rationale": "policy"}'
    monkeypatch.setattr(mod, "get_llm", lambda: FakeLLM(reply))
    decision = asyncio.run(route("Tell me about the headphones", "analyst"))
    assert (decision.intent, decision.rationale) == ("docs_rag", "policy")


@pytest.mark.parametrize("reply", ["not json", '{"intent": "bogus"}', "[1]"])
def test_malformed_llm_reply_on_ambiguous_query_defaults_to_review_rag(monkeypatch, reply):
    monkeypatch.setattr(mod, "get_llm", lambda: FakeLLM(reply))
    decision = asyncio.run(route("Tell me about the headphones", "analyst"))
    assert (decision.intent, decision.rationale) == ("review_rag", mod.DEFAULT_RATIONALE)


def test_rule_hit_wins_and_llm_is_not_called(monkeypatch):
    llm = FakeLLM('{"intent": "review_rag", "rationale": "wrong"}')
    calls = []

    async def spy(system, user, *, ledger, max_tokens=None):
        calls.append(user)
        return llm.reply

    llm.complete = spy
    monkeypatch.setattr(mod, "get_llm", lambda: llm)
    decision = asyncio.run(route("how many reviews per category", "analyst"))
    assert decision.intent == "sql"
    assert calls == []
