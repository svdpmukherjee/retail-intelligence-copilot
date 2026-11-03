"""Focused regressions; fixture adapters forbid sockets and serving DB access."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from agents import pipeline
from agents.composer import AnswerResult, Citation
from agents.query_plan import independent_questions
from eval.quality_baseline import environment
from eval.quality_fixture import load_fixture
from governance.grounding import citation_numbers

PRODUCT = "Why are our lowest-rated electronics disappointing customers?"
POLICY = "What does our return policy say about damaged items?"
COMBINED = PRODUCT + " and " + POLICY
EXPLICIT = (
    PRODUCT.rstrip("?")
    + " using lowest average ratings with at least 2 reviews, show 1? and "
    + POLICY
)


@pytest.fixture(autouse=True)
def bounded_environment():
    with environment("fixture", load_fixture()):
        yield


@pytest.mark.parametrize("separator", [" and ", " ", "\n", "; "])
def test_explicit_questions_split_but_subjects_are_preserved(separator):
    assert independent_questions(PRODUCT + separator + POLICY) == [PRODUCT, POLICY]


@pytest.mark.parametrize(
    "query",
    [
        "What do customers say about Toys and Electronics?",
        "What are our return and refund policies?",
        "Which products are lowest-rated and why?",
        PRODUCT + " And why is that?",
        PRODUCT + " And what about their returns?",
    ],
)
def test_lists_and_dependent_clauses_remain_intact(query):
    assert independent_questions(query) == [query]


def test_reported_combination_runs_all_three_tools_with_independent_scopes():
    result = asyncio.run(pipeline.answer(EXPLICIT, "marketing"))
    assert result.audit["tool_path"] == ["sql_agent", "review_rag", "docs_rag"]
    assert result.audit["parts"][0]["query_filters"]["category"] == ["Electronics"]
    assert len(result.audit["parts"][1]["query_filters"]["category"]) == 3
    assert result.sql and result.sql.rows
    assert {c.n for c in result.citations} == citation_numbers(result.answer)
    assert any(c.source_id == "sql" for c in result.citations)
    assert any("policy" in c.display_label.lower() for c in result.citations)
    assert "couldn't calculate" not in result.answer


def test_denied_category_does_not_block_or_widen_policy_part():
    result = asyncio.run(
        pipeline.answer(
            "Why are our lowest-rated Books disappointing customers? and " + POLICY, "marketing"
        )
    )
    assert result.audit["parts"][0]["query_filters"]["category"] == []
    assert result.audit["parts"][0]["sources"] == []
    assert result.citations and all(c.source_id != "sql" for c in result.citations)


def test_failed_part_keeps_successful_policy(monkeypatch):
    def fail(*args):
        raise RuntimeError("bounded adapter failure")

    monkeypatch.setattr(pipeline, "review_rag", fail)
    result = asyncio.run(pipeline.answer(EXPLICIT, "executive"))
    assert "couldn't answer this part" in result.answer
    assert result.citations and "Question 2" in result.answer


def test_grouped_citations_are_renumbered_even_when_original_numbers_have_gaps():
    def part():
        return AnswerResult(
            answer="Supported [1, 3].",
            citations=[
                Citation(n=n, source_id=str(n), label="s", display_label="Source") for n in (1, 3)
            ],
            audit={},
        )

    combined = pipeline._combine_answers([part(), part()])
    assert "[1, 2]" in combined.answer and "[3, 4]" in combined.answer
    assert [c.n for c in combined.citations] == [1, 2, 3, 4]


def test_shared_budget_and_single_persisted_chat_turn(monkeypatch):
    original = pipeline._execute_question
    ledgers = []

    async def execute(query, role, ledger, **kwargs):
        ledgers.append(ledger)
        ledger.add(1, 0)
        return await original(query, role, ledger, **kwargs)

    persist = AsyncMock(return_value=0)
    monkeypatch.setattr(pipeline, "_execute_question", execute)
    from memory.manager import MemoryManager

    monkeypatch.setattr(MemoryManager, "persist", persist)
    result = asyncio.run(pipeline.answer(EXPLICIT, "executive", thread_id="t", user_id="u"))
    assert len(ledgers) == 2 and ledgers[0] is ledgers[1]
    assert result.audit["tokens"] == 2
    persist.assert_awaited_once()
    assert "error" not in result.audit["memory"]


def test_too_many_questions_asks_for_bounded_request(monkeypatch):
    execute = AsyncMock()
    monkeypatch.setattr(pipeline, "_execute_question", execute)
    result = asyncio.run(pipeline.answer(" and ".join([POLICY] * 5), "executive"))
    assert result.kind == "clarification" and "four" in result.answer
    execute.assert_not_called()


def test_most_common_complaint_request_explicitly_discloses_missing_rank():
    result = asyncio.run(
        pipeline.answer("What do customers complain about most in their reviews?", "executive")
    )
    assert "can't determine which issues are most common" in result.answer


def test_numeric_display_modifier_stays_with_original_question():
    from agents.query_plan import independent_questions

    query = (
        "Why are the lowest average Electronics products disappointing customers? "
        "Use at least 2 reviews and show 1."
    )
    assert independent_questions(query) == [query]


def test_replacement_metric_keeps_explicit_new_category_in_fallback():
    from agents.conversation import _fallback_parts
    from agents.query_plan import requested_categories
    from memory.manager import MemoryContext

    context = MemoryContext(
        thread_id="replacement",
        pending_clarification=True,
        clarify_subject="Which Electronics products have the highest revenue?",
    )
    parts = _fallback_parts("most-reviewed Toys products", context)
    assert requested_categories(parts[0].query) == ["Toys_and_Games"]
    assert "revenue" not in parts[0].query
