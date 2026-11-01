import asyncio

import pytest

from agents.composer import MAX_QUOTE_CHARS, _snippet, _truncate, compose
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


def test_sql_block_rounds_redacts_and_caps_at_the_query_bound() -> None:
    from agents.composer import MAX_SQL_ROWS_SHOWN

    # A modest result (15 rows) must show in FULL -- the old 10-row display cap silently
    # dropped rows the query kept (B-10 follow-up).
    rows = [[f"user{i}@example.com", i + 0.123456] for i in range(15)]
    sql = {"sql": "select 1", "columns": ["who", "score"], "rows": rows}
    result = asyncio.run(compose("q", sql, [], CostLedger()))
    assert result.citations[0].source_id == "sql"
    assert result.sql is not None and result.sql.sql == "select 1"
    assert len(result.sql.rows) == 15 and result.sql.total_rows == 15
    assert result.sql.rows[0] == ["[EMAIL]", 0.12]  # redacted + rounded to 2dp

    # Past the display bound, rows are capped but total_rows reports the full count so the
    # UI can say "showing X of Y".
    big = [[f"u{i}@x.com", float(i)] for i in range(MAX_SQL_ROWS_SHOWN + 5)]
    capped = asyncio.run(
        compose("q", {"sql": "s", "columns": ["who", "n"], "rows": big}, [], CostLedger())
    ).sql
    assert len(capped.rows) == MAX_SQL_ROWS_SHOWN and capped.total_rows == MAX_SQL_ROWS_SHOWN + 5


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


def test_truncate_leaves_short_text_unchanged() -> None:
    assert _truncate("battery  dies\nfast") == "battery dies fast"


def test_truncate_cuts_at_word_boundary_with_ellipsis() -> None:
    words = ["battery"] * 60
    out = _truncate(" ".join(words))
    assert out.endswith("…")
    assert len(out) <= MAX_QUOTE_CHARS + 1
    assert set(out[:-1].split()) == {"battery"}


def test_truncate_hard_cuts_single_long_token() -> None:
    out = _truncate("x" * (MAX_QUOTE_CHARS * 3))
    assert out == "x" * MAX_QUOTE_CHARS + "…"


def test_snippet_of_long_review_does_not_end_mid_word() -> None:
    snippet = _snippet("lovely " * 100)
    assert snippet is not None and snippet.endswith("lovely…")
