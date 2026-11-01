import asyncio

import pytest

from agents.composer import compose
from app.cost import CostLedger
from governance.grounding import enforce_grounding
from retrieval.schema import Chunk, SearchHit


class NoLLM:
    available = False


@pytest.fixture(autouse=True)
def extractive(monkeypatch):
    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())


def _hit(cid: str, text: str) -> SearchHit:
    chunk = Chunk(id=cid, source_type="review", text=text, asin="B01", category="Electronics")
    return SearchHit(chunk=chunk, score=1.0)


def test_extractive_answer_cites_only_returned_sources() -> None:
    sql = {"sql": "select 1", "columns": ["n"], "rows": [[3]]}
    result = asyncio.run(
        compose("q", sql, [_hit("c1", "battery dies fast"), _hit("c2", "too loud")], CostLedger())
    )

    assert [c.source_id for c in result.citations] == ["sql", "c1", "c2"]
    assert enforce_grounding(result.answer, {c.n for c in result.citations}) == []
    assert result.audit["grounding"]["path"] == "extractive"


def test_no_evidence_yields_no_citations() -> None:
    result = asyncio.run(compose("q", None, [], CostLedger()))
    assert result.citations == []
    assert "No supporting evidence" in result.answer


def test_dangling_and_uncited_claims_are_flagged() -> None:
    issues = enforce_grounding("Good battery [1].\nMade up claim.\nAnother [7].", {1})
    assert "dangling citation [7]" in issues
    assert any(i.startswith("uncited claim") for i in issues)


def test_uncited_llm_draft_is_blocked_and_falls_back(monkeypatch) -> None:
    class BadLLM:
        available = True

        async def complete(self, system, user, *, ledger, max_tokens=None):
            return "Customers love it [9]."

    monkeypatch.setattr("agents.composer.get_llm", lambda: BadLLM())
    result = asyncio.run(compose("q", None, [_hit("c1", "battery dies fast")], CostLedger()))

    assert result.audit["grounding"]["path"] == "extractive"
    assert "dangling citation [9]" in result.audit["grounding"]["issues"]
    assert [c.source_id for c in result.citations] == ["c1"]


def test_sql_block_matches_cited_citation_rounded_capped_and_redacted() -> None:
    rows = [[f"user{i}@example.com", i + 0.123456] for i in range(15)]
    sql = {"sql": "select 1", "columns": ["who", "score"], "rows": rows}
    result = asyncio.run(compose("q", sql, [], CostLedger()))

    assert result.citations[0].source_id == "sql"
    assert result.sql is not None and result.sql.sql == "select 1"
    assert len(result.sql.rows) == 10
    assert result.sql.rows[0] == ["[EMAIL]", 0.12]


def test_sql_block_absent_without_sql_or_when_sql_citation_dropped(monkeypatch) -> None:
    assert asyncio.run(compose("q", None, [_hit("c1", "loud")], CostLedger())).sql is None

    class Llm:
        available = True

        async def complete(self, system, user, *, ledger):
            return "Only the review says it is loud [2]"

    monkeypatch.setattr("agents.composer.get_llm", lambda: Llm())
    sql = {"sql": "select 1", "columns": ["n"], "rows": [[3]]}
    result = asyncio.run(compose("q", sql, [_hit("c1", "loud")], CostLedger()))
    assert [c.n for c in result.citations] == [2]
    assert result.sql is None
