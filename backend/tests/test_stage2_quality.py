"""Stage 2 semantic contracts using real routing, SQL, fusion and composition.

External adapters are bounded fixtures; no DB writes, network or hosted generation.
"""

import asyncio
from unittest.mock import patch

import pytest

from agents import pipeline, query_plan, sql_agent
from agents.composer import compose
from agents.router import route
from app.cost import CostLedger
from eval import quality_baseline as baseline
from eval.quality_fixture import load_fixture
from memory.manager import MemoryContext, Turn, effective_query
from retrieval.vector_store import build_where


@pytest.fixture(autouse=True)
def bounded_environment():
    with baseline.environment("fixture", load_fixture()):
        yield


def answer(query, role="executive"):
    return asyncio.run(pipeline.answer(query, role))


def context(question, pending=False):
    return MemoryContext(
        thread_id="t",
        history=[Turn(role_kind="user", content=question)],
        pending_clarification=pending,
        clarify_subject=question if pending else None,
    )


@pytest.mark.parametrize(
    "query",
    [
        "Why are customers unhappy with our lowest-rated toys?",
        (
            "Why are our lowest-rated electronics disappointing customers "
            "using lowest average ratings with at least 2 reviews, show 1?"
        ),
        "What does our return policy say about damaged items?",
        "What's the average customer rating by category?",
    ],
)
def test_standalone_topic_survives_history_and_pending_clarification(query):
    for pending in (False, True):
        assert effective_query(query, context("highest revenue?", pending)) == query


def test_genuine_followup_and_clarification_reply_keep_context():
    assert effective_query(
        "Why is that?", context("Which Electronics products are lowest-rated?")
    ).startswith("Which Electronics")
    assert effective_query("most-reviewed products", context("highest revenue?", True)).endswith(
        "most-reviewed products"
    )
    assert effective_query("average rating?", context("highest revenue?")) == "average rating?"


def test_category_switch_replaces_old_subject_and_permissions_never_widen():
    query = effective_query(
        "What about Books?", context("What's the average rating by category for Electronics?")
    )
    decision = asyncio.run(route(query, "marketing"))
    assert decision.scope["category"]  # role scope preserved separately
    assert decision.filters["category"] == []
    result = answer(query, "marketing")
    assert result.citations == [] and result.sql is None
    assert result.audit["sources"] == [] and result.audit["sql_outcome"] == "empty"


@pytest.mark.parametrize(
    "query, category",
    [
        ("What do customers praise about Beauty products?", "Beauty_and_Personal_Care"),
        (
            (
                "Why are our lowest-rated toys disappointing customers "
                "using lowest average ratings with at least 2 reviews, show 1?"
            ),
            "Toys_and_Games",
        ),
        ("What do customers say about Books?", "Books"),
    ],
)
def test_requested_categories_are_canonical_and_applied_before_retrieval(query, category):
    with baseline.capture() as observed:
        result = answer(query)
    assert observed["retrieved"]
    assert {h["category"] for h in observed["retrieved"]} == {category}
    assert result.audit["query_filters"]["category"] == [category]


def test_category_averages_match_independent_review_gold_without_model_sql():
    fixture = load_fixture()
    with patch.object(sql_agent, "generate_sql", side_effect=AssertionError("Not generated")):
        result = asyncio.run(
            sql_agent.sql_agent("What's the average customer rating by category?", {}, CostLedger())
        )
    ci, vi = result["columns"].index("category"), result["columns"].index("avg_rating")
    assert {r[ci]: r[vi] for r in result["rows"]} == fixture["averages"]
    assert result["status"] == "success" and not result["has_more"]
    assert "AVG(rating)" in result["sql"] and "product_avg_rating" not in result["sql"]


@pytest.mark.parametrize(
    "query",
    [
        "average rating by category in 2023",
        "average rating by category for verified reviews",
        "lowest-rated Electronics last year",
        "average product-level rating by category",
    ],
)
def test_specialized_templates_do_not_drop_unsupported_constraints(query):
    assert query_plan.rating_operation(query) is None


def test_lowest_selection_uses_all_reviews_minimum_count_and_product_id():
    with baseline.capture() as observed:
        result = answer(
            "Why are our lowest-rated Electronics disappointing customers "
            "using lowest average ratings with at least 2 reviews, show 1?"
        )
    selected = observed["sql"]
    assert observed["decision"]["intent"] == "sql_rag"
    assert result.audit["tool_path"] == ["sql_agent", "review_rag"]
    assert observed["selected_product_ids"] == ["E-low"]
    assert {h["asin"] for h in observed["retrieved"]} == {"E-low"}
    assert selected["minimum_review_count"] == 2
    assert selected["product_limit"] == 1 and "rating <=" not in selected["sql"]
    assert "COUNT(*) >= 2" in selected["sql"]


def test_toy_followup_no_longer_repeats_category_averages():
    query = effective_query(
        "Why is that?",
        context(
            "Which Toys products have the lowest average ratings with at least 2 reviews, show 1?"
        ),
    )
    with baseline.capture() as observed:
        result = answer(query)
    assert result.audit["tool_path"] == ["sql_agent", "review_rag"]
    assert {h["category"] for h in observed["retrieved"]} == {"Toys_and_Games"}
    assert "GROUP BY asin, category" in observed["sql"]["sql"]


def test_missing_product_evidence_is_disclosed_without_other_products(monkeypatch):
    filters = []

    def no_matches(query, scope):
        filters.append(scope)
        return []

    monkeypatch.setattr(pipeline, "review_rag", no_matches)
    result = answer(
        "Why are our lowest-rated Electronics disappointing customers "
        "using lowest average ratings with at least 2 reviews, show 1?"
    )
    assert filters[0]["asin"] == ["E-low"]
    assert result.audit["grounding"]["path"] == "selection_only"
    assert "matching review passages" in result.answer
    assert result.sql and [c.source_id for c in result.citations] == ["sql"]


@pytest.mark.parametrize("outcome", ["empty", "failure", "missing_ids", "null_ids"])
def test_selection_failure_or_empty_never_broadens_to_other_reviews(monkeypatch, outcome):
    async def selection(*args, **kwargs):
        if outcome == "failure":
            raise sql_agent.SQLComputeError("failed")
        return {
            "sql": "SELECT ...",
            "columns": ["asin"] if outcome == "null_ids" else ["product_title"],
            "rows": (
                [] if outcome == "empty" else [[None if outcome == "null_ids" else "unidentified"]]
            ),
        }

    monkeypatch.setattr(pipeline, "sql_agent", selection)
    monkeypatch.setattr(pipeline, "review_rag", lambda *args: pytest.fail("Broad retrieval"))
    result = answer(
        "Why are our lowest-rated Electronics disappointing customers "
        "using lowest average ratings with at least 2 reviews, show 1?"
    )
    assert result.sql is None and result.citations == []
    assert "no rows" not in result.answer and "[1]" not in result.answer
    assert result.audit["sql_outcome"] == ("empty" if outcome == "empty" else "failure")


def test_empty_sql_cannot_become_a_source_even_with_old_memory():
    memory = context("Electronics average was 4.9")
    result = asyncio.run(
        compose(
            "q", {"sql": "s", "rows": [], "columns": ["asin"]}, [], CostLedger(), context=memory
        )
    )
    assert result.sql is None and result.citations == []
    assert "4.9" not in result.answer and "matching results" in result.answer


def test_repair_gets_previous_sql_and_redacted_error(monkeypatch):
    calls = []

    class Script:
        available = True

        async def complete(self, system, user, **kwargs):
            calls.append((system, user))
            return (
                "SELECT missing FROM structured"
                if len(calls) == 1
                else "SELECT COUNT(*) AS n FROM structured"
            )

    monkeypatch.setattr(sql_agent, "get_llm", lambda **kwargs: Script())
    result = asyncio.run(sql_agent.sql_agent("How many reviews?", {}, CostLedger()))
    assert result["rows"] == [[12]]
    assert "Previous attempt failed" not in calls[0][1]
    assert "<failed_sql>SELECT missing FROM structured</failed_sql>" in calls[1][1]
    assert "BinderException" in calls[1][1]
    assert "ONE review" in calls[0][0] and "canonical" in calls[0][0]


def test_sql_fetch_reports_overflow_and_empty_filter_is_not_unrestricted():
    result = sql_agent.run_sql("SELECT * FROM structured, range(25)")
    assert len(result["rows"]) == sql_agent.MAX_ROWS and result["has_more"] is True
    assert sql_agent.run_sql("SELECT * FROM structured", {"category": []})["rows"] == []
    assert sql_agent.run_sql("SELECT * FROM structured", {"category": "Electronics"})["rows"]
    # The optional SQL block flag survives the display cap.
    out = asyncio.run(compose("q", result, [], CostLedger()))
    assert out.sql.has_more and out.sql.total_rows == sql_agent.MAX_ROWS


def test_asin_filter_is_parameterized_and_empty_list_means_no_match():
    where, params = build_where({"asin": ["x'; DROP TABLE chunks; --"], "category": []})
    assert "DROP" not in where and params == [["x'; DROP TABLE chunks; --"], []]
    assert "asin = ANY(%s)" in where and "category = ANY(%s)" in where


def test_unknown_explicit_category_yields_empty_selection():
    result = answer(
        "Why are our lowest-rated UnknownCategory products disappointing customers "
        "using lowest average ratings with at least 2 reviews, show 1?"
    )
    assert result.audit["sql_outcome"] == "empty"
    assert result.sql is None and result.citations == []


def test_excluded_categories_are_removed_within_role_scope():
    filters = query_plan.constrained_scope(
        "average rating by category except Beauty and Toys",
        {"category": ["Electronics", "Beauty_and_Personal_Care", "Toys_and_Games"]},
    )
    assert filters["category"] == ["Electronics"]
    filters = query_plan.constrained_scope("Beauty reviews excluding Beauty", {})
    assert filters["category"] == []


@pytest.mark.parametrize(
    "query",
    [
        "lowest-rated products with at least 10 reviews",
        "lowest-rated products per category",
        "average rating by category with 5 stars",
    ],
)
def test_numeric_or_partition_constraints_do_not_use_unqualified_templates(query):
    assert query_plan.rating_operation(query) is None


@pytest.mark.parametrize(
    "query",
    [
        "average rating by category for Acme products",
        "lowest-rated Electronics from Acme",
        "average product rating by category",
        "average product_avg_rating by category",
    ],
)
def test_unknown_qualifier_or_explicit_product_metric_stays_on_generated_sql_path(query):
    assert query_plan.rating_operation(query) is None


def test_explicit_unrecognized_category_does_not_search_everything():
    filters = query_plan.constrained_scope("What do customers say in the Furniture category?", {})
    assert filters["category"] == ["Furniture"]
    result = answer("What do customers say in the Furniture category?")
    assert result.citations == []
    assert query_plan.constrained_scope("average rating for each category", {}) == {}


def test_explicit_category_review_counts_use_exact_scoped_rows_without_model_sql(monkeypatch):
    monkeypatch.setattr(sql_agent, "generate_sql", lambda *a, **k: pytest.fail("No generated SQL"))
    result = asyncio.run(
        sql_agent.sql_agent(
            "How many reviews are there per category?", {"category": ["Electronics"]}, CostLedger()
        )
    )
    assert result["rows"] == [["Electronics", 4]]
    assert query_plan.rating_operation("How many reviews per category in 2023?") is None
