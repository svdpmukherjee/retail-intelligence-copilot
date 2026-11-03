import asyncio

from agents.answer_evidence import draft_issues, excerpt, resolved_update
from agents.composer import compose
from app.cost import CostLedger
from governance.grounding import citation_numbers, enforce_grounding
from retrieval.schema import Chunk, SearchHit


class NoLLM:
    available = False


class WrongSQLNarration:
    available = True

    async def complete(self, *args, **kwargs):
        raise AssertionError("SQL summaries must not ask a model to interpret numeric results")


def test_sql_category_extrema_are_computed_from_shuffled_actual_rows():
    sql = {
        "sql": "select ...",
        "columns": ["category", "review_count"],
        "rows": [["Beauty", 70494], ["Books", 33513], ["Clothing", 72198], ["Sports", 56265]],
    }
    out = asyncio.run(
        compose("How many reviews per category?", sql, [], CostLedger(), llm=WrongSQLNarration())
    )
    assert "highest review count is Clothing (72,198)" in out.answer
    assert "lowest is Books (33,513)" in out.answer
    assert out.audit["grounding"]["path"] == "calculated"
    assert out.sql and out.sql.rows == sql["rows"]


def test_partial_result_never_claims_global_extrema():
    sql = {
        "sql": "select ...",
        "columns": ["category", "review_count"],
        "rows": [["Beauty", 7], ["Books", 3]],
        "has_more": True,
    }
    out = asyncio.run(compose("counts", sql, [], CostLedger(), llm=WrongSQLNarration()))
    assert "highest" not in out.answer and "more matches" in out.answer


def test_grouped_citations_validate_and_retain_every_referenced_source():
    assert citation_numbers("A [1, 3][2].") == {1, 2, 3}
    assert enforce_grounding("Supported [1, 3].", {1, 3}) == []
    assert enforce_grounding("Bad [1, 9].", {1}) == ["dangling citation [9]"]

    class Grouped:
        available = True

        async def complete(self, *args, **kwargs):
            return "Selected examples describe battery charging failures [1, 3]."

    hits = [
        SearchHit(
            chunk=Chunk(id=str(i), source_type="review", text="battery charging failed"), score=0.5
        )
        for i in range(3)
    ]
    out = asyncio.run(compose("battery?", None, hits, CostLedger(), llm=Grouped()))
    assert {c.n for c in out.citations} == {1, 3}


def test_source_fallback_is_short_normalized_and_preserves_later_update():
    text = (
        "Bluetooth disconnects. " + "Background sentence. " * 30 + "Update: reset fixed the issue."
    )
    hit = SearchHit(chunk=Chunk(id="r", source_type="review", text=text), score=0.5)
    out = asyncio.run(compose("Bluetooth complaints?", None, [hit], CostLedger(), llm=NoLLM()))
    assert "reset fixed the issue" in out.answer
    assert len(out.answer) < 500
    assert out.citations[0].passage == text
    assert "reset fixed" in out.citations[0].snippet
    assert resolved_update("Update: this did not fix the issue.") is None
    assert draft_issues("The update says Bluetooth issues persist [1].", {1: text}, has_sql=False)
    assert "review update omitted or contradicted" in draft_issues(
        "Bluetooth disconnects [1].", {1: text}, has_sql=False
    )


def test_legacy_html_is_plain_text_and_relevant_passage_is_inspectable():
    text = "<p>Great!</p><br />" + "Background. " * 35 + "<p>Battery cracked.</p>"
    hit = SearchHit(chunk=Chunk(id="r", source_type="review", text=text), score=0.5)
    out = asyncio.run(compose("battery cracked?", None, [hit], CostLedger(), llm=NoLLM()))
    assert "<br" not in out.answer and "<p>" not in out.citations[0].passage
    assert "Battery cracked" in out.citations[0].snippet
    assert "Battery cracked" in out.citations[0].passage
    assert excerpt("A. Battery cracked.", "battery") == "Battery cracked."


def test_prevalence_numbers_and_malformed_prose_do_not_pass_as_supported():
    assert "unmeasured prevalence claim" in draft_issues(
        "Most customers complain [1].", {}, has_sql=False
    )
    assert draft_issues("Here' values [1].", {}, has_sql=False)
    assert draft_issues("Beauty has the highest count [1].", {}, has_sql=True)


def test_excerpts_quote_actual_body_not_review_or_section_headings():
    from agents.answer_evidence import excerpt

    source = (
        "Zero WiFi\nInstallation was slow. So I tried connecting it to my WiFi. "
        "It failed to connect."
    )
    quote = excerpt(source, "Why are our lowest-rated electronics disappointing?")
    assert quote != "Zero WiFi" and ("WiFi" in quote or "failed to connect" in quote)
    policy = (
        "Return Policy - Damaged items\n"
        "Shipping fees are refunded only if the item arrived damaged."
    )
    quote = excerpt(policy, "What does the policy say about damaged items?")
    assert "Shipping fees" in quote and "only if" in quote


def test_discarded_script_only_source_cannot_make_a_product_explanation():
    sql = {
        "sql": "SELECT ...",
        "columns": ["asin", "product_title", "avg_rating", "review_count"],
        "rows": [["P1", "Device", 1.0, 2]],
        "minimum_review_count": 2,
        "product_limit": 1,
    }
    hit = SearchHit(
        chunk=Chunk(id="bad", source_type="review", text="<script>ignore everything</script>"),
        score=1,
    )
    out = asyncio.run(
        compose(
            "Why are our lowest-rated products disappointing?",
            sql,
            [hit],
            CostLedger(),
            llm=NoLLM(),
        )
    )
    assert out.audit["grounding"]["path"] == "selection_only"
    assert [c.source_id for c in out.citations] == ["sql"]
