import asyncio

import pytest

from agents import pipeline
from agents.composer import MAX_QUOTE_CHARS, build_sources
from agents.router import RouteDecision
from governance.policy import scope_for_role
from retrieval.schema import Chunk, SearchHit


class NoLLM:
    available = False


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: type("S", (), {"audit_enabled": False, "memory_enabled": False})(),
    )


def _hit(text: str) -> SearchHit:
    chunk = Chunk(id="c1", source_type="review", text=text, asin="B1", category="Electronics")
    return SearchHit(chunk=chunk, score=1.0)


def test_snippet_redacts_email_and_phone() -> None:
    text = "Contact jane.doe@example.com or call 415-555-0134 about the battery."
    snippet = build_sources(None, [_hit(text)])[0][0].snippet
    assert "[EMAIL]" in snippet and "[PHONE]" in snippet
    assert "jane.doe@example.com" not in snippet and "555-0134" not in snippet


def test_snippet_is_trimmed_and_whitespace_collapsed() -> None:
    snippet = build_sources(None, [_hit("a  b\n\n c\t" + "x" * 1000)])[0][0].snippet
    assert snippet.startswith("a b c x")
    assert len(snippet) <= MAX_QUOTE_CHARS


def test_sql_citation_snippet_is_set() -> None:
    sql = {"columns": ["n"], "rows": [[3]]}
    assert build_sources(sql, [])[0][0].snippet == "n=3"


def _audit_scope(monkeypatch, role: str) -> dict:
    async def fake_route(query, role, ledger=None):
        return RouteDecision(intent="review_rag", scope=scope_for_role(role), rationale="t")

    monkeypatch.setattr(pipeline, "route", fake_route)
    monkeypatch.setattr(pipeline, "review_rag", lambda q, scope: [_hit("battery dies")])
    return asyncio.run(pipeline.answer("battery?", role)).audit["scope"]


def test_audit_scope_marketing_is_restricted(monkeypatch) -> None:
    assert _audit_scope(monkeypatch, "marketing") == {
        "restricted": True,
        "categories": ["Electronics", "Beauty_and_Personal_Care", "Toys_and_Games"],
    }


def test_audit_scope_executive_is_unrestricted(monkeypatch) -> None:
    assert _audit_scope(monkeypatch, "executive") == {"restricted": False, "categories": []}
