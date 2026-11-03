"""Reported conversational failures: real pipeline, tiny adapters, no network/DB writes."""

import asyncio
import json

import pytest

from agents import composer, pipeline
from agents.composer import AnswerResult, Citation, synthesize_answers
from agents.conversation import understand
from agents.product_criteria import ProductCriteria
from agents.suggestions import render_suggestions
from app.cost import CostLedger
from eval.quality_baseline import capture, environment
from eval.quality_fixture import load_fixture
from memory.manager import MemoryManager


@pytest.fixture(autouse=True)
def bounded():
    with environment("fixture", load_fixture()):
        yield


def answer(query, role="marketing", **kwargs):
    return asyncio.run(pipeline.answer(query, role, **kwargs))


@pytest.mark.parametrize(
    "query,role,expected",
    [
        ("hello", "support", "Retail Intelligence Copilot"),
        ("which products my jo roles haas access to?", "marketing", "Beauty and Personal Care"),
        ("job roles?", "marketing", "Your marketing role"),
        ("write a python programming for 2+2", "support", "outside this copilot"),
        ("python code", "support", "outside this copilot"),
        (
            "What do customers dislike about Automotive?",
            "marketing",
            "doesn't have access to Automotive",
        ),
        (
            "What do customers praise about home & kitchen products?",
            "marketing",
            "doesn't have access to Home and Kitchen",
        ),
        (
            "What do customers praise about Beauty products?",
            "support",
            "doesn't have access to Beauty",
        ),
    ],
)
def test_control_and_forbidden_requests_do_not_retrieve(query, role, expected, monkeypatch):
    for tool in ("review_rag", "docs_rag", "sql_agent"):
        monkeypatch.setattr(pipeline, tool, lambda *a, **k: pytest.fail("Unexpected tool"))
    result = answer(query, role)
    assert expected in result.answer
    assert result.citations == [] and result.audit["tool_path"] == []
    assert result.audit["grounding"]["path"] == "conversation"
    assert result.suggestions


def test_typo_and_category_followup_keep_scope_and_positive_intent():
    result = answer(
        "What do customers praise about automative products?", "support", thread_id="t", user_id="u"
    )
    assert result.audit["query_filters"]["category"] == ["Automotive"]
    with capture() as observed:
        result = answer("how about Pet Supplies?", "support", thread_id="t", user_id="u")
    assert result.audit["query_filters"]["category"] == ["Pet_Supplies"]
    assert "praise" in observed["resolved_query"].lower()


def test_lowest_clarification_replay_invalid_reply_threshold_and_companion_policy():
    query = (
        "Why are our lowest-rated Electronics disappointing customers? "
        "and What does our return policy say about damaged items?"
    )
    first = answer(query, thread_id="t", user_id="u")
    assert first.kind == "clarification" and not first.citations
    assert len(first.clarification_state["parts"]) == 2
    assert first.suggestions and first.audit["tool_path"] == []
    replay = MemoryManager._render_payload(first)
    assert replay["clarification_state"] == first.clarification_state
    invalid = answer("both", thread_id="t", user_id="u")
    assert invalid.kind == "clarification" and invalid.audit["tool_path"] == []
    result = answer(
        "Show five products averaging below 2 with at least 2 reviews", thread_id="t", user_id="u"
    )
    assert result.kind == "answer"
    assert result.audit["tool_path"] == ["sql_agent", "review_rag", "docs_rag"]
    assert "AVG(rating) < 2.0" in result.sql.sql and "COUNT(*) >= 2" in result.sql.sql
    assert "averaging below 2/5" in result.answer
    assert all(row[result.sql.columns.index("avg_rating")] < 2 for row in result.sql.rows)


def test_new_topic_cancels_pending_selection():
    answer(
        "Why are our lowest-rated Electronics disappointing customers?", thread_id="t", user_id="u"
    )
    result = answer("What is our return policy?", thread_id="t", user_id="u")
    assert result.kind == "answer" and result.audit["tool_path"] == ["docs_rag"]


def test_threshold_and_minimum_can_be_supplied_in_separate_short_replies():
    answer(
        "Why are our lowest-rated Electronics disappointing customers?", thread_id="t", user_id="u"
    )
    threshold = answer("below 2", thread_id="t", user_id="u")
    assert threshold.kind == "clarification" and "minimum review count" in threshold.answer
    result = answer("2", thread_id="t", user_id="u")
    assert result.kind == "answer" and "AVG(rating) < 2.0" in result.sql.sql


def test_selection_does_not_silently_discard_date_or_brand_conditions():
    for qualifier in ("last year", "from Acme", "for verified reviews"):
        result = answer(
            "Why are our lowest-rated Electronics disappointing customers "
            "using lowest average ratings with at least 2 reviews " + qualifier + "?"
        )
        assert result.kind == "clarification" and not result.audit["tool_path"]


def test_access_question_companion_does_not_hide_policy_question():
    result = answer(
        "Which products does my job role have access to? and What is our return policy?"
    )
    assert result.audit["tool_path"] == ["docs_rag"]
    assert "Your marketing role" in result.answer and result.citations


def test_numeric_selection_uses_all_ratings_not_just_negative_rows():
    from agents.sql_agent import sql_agent

    result = asyncio.run(
        sql_agent(
            "Electronics",
            {"category": ["Electronics"]},
            CostLedger(),
            selection=ProductCriteria(minimum_reviews=2, limit=5, mode="below", average_below=2),
        )
    )
    assert "WHERE" in result["sql"] and "rating <=" not in result["sql"]
    assert "AVG(rating) < 2.0" in result["sql"]
    assert all(row[result["columns"].index("asin")] == "E-low" for row in result["rows"])


class Script:
    available = True

    def __init__(self, payload):
        self.payload = payload

    async def complete(self, *args, **kwargs):
        return json.dumps(self.payload)


def test_model_cannot_rewrite_away_requested_category_or_exclusion():
    llm = Script(
        {
            "action": "execute",
            "parts": [
                {"query": "What do customers praise about Electronics?", "intent": "review_rag"}
            ],
        }
    )
    plan = asyncio.run(
        understand(
            "What do customers praise about Beauty excluding Toys?",
            "marketing",
            None,
            CostLedger(),
            llm=llm,
        )
    )
    assert plan.parts[0].query == "What do customers praise about Beauty excluding Toys?"


def test_large_planner_typed_output_routes_policy_and_malformed_output_falls_back():
    query = "What does our return policy say about damaged items?"
    llm = Script({"action": "execute", "parts": [{"query": query, "intent": "docs_rag"}]})
    plan = asyncio.run(understand(query, "marketing", None, CostLedger(), llm=llm))
    assert plan.parts[0].intent == "docs_rag"
    bad = Script({"action": "execute", "parts": []})
    plan = asyncio.run(understand(query, "marketing", None, CostLedger(), llm=bad))
    assert plan.parts[0].query == query


def test_suggestions_cannot_offer_forbidden_or_unknown_categories():
    actions = [
        {"action": "praise", "category": "Automotive"},
        {"action": "praise", "category": "Imaginary"},
    ]
    suggestions = render_suggestions("marketing", "Beauty reviews", actions)
    assert len(suggestions) <= 3
    assert not any("Automotive" in q or "Imaginary" in q for q in suggestions)
    assert any("Beauty" in q for q in suggestions)


def test_final_synthesis_rejects_cross_part_citations_and_keeps_supported_draft(monkeypatch):
    original = AnswerResult(
        answer="Verified excerpt [2].",
        citations=[
            Citation(
                n=2,
                source_id="review",
                label="review x",
                display_label="Review",
                passage="Battery failed.",
            )
        ],
        audit={"grounding": {"path": "extractive", "issues": []}},
    )
    monkeypatch.setattr(
        composer,
        "get_llm",
        lambda **k: Script({"answers": [{"part": 0, "answer": "Invented [99]."}]}),
    )
    result = asyncio.run(synthesize_answers([original], ["Why?"], CostLedger()))
    assert result[0].answer == "Verified excerpt [2]."
    monkeypatch.setattr(
        composer,
        "get_llm",
        lambda **k: Script(
            {"answers": [{"part": 0, "answer": "The review reports battery failure [2]."}]}
        ),
    )
    result = asyncio.run(synthesize_answers([original], ["Why?"], CostLedger()))
    assert "battery failure [2]" in result[0].answer
    assert result[0].audit["grounding"]["path"] == "llm"
