import asyncio

from agents.composer import compose
from app.cost import CostLedger
from governance.grounding import enforce_grounding
from retrieval.schema import Chunk, SearchHit


def _hit() -> SearchHit:
    chunk = Chunk(id="c1", source_type="review", text="battery dies fast", asin="B01", category="E")
    return SearchHit(chunk=chunk, score=1.0)


def test_gate_blocks_dangling_citation() -> None:
    assert enforce_grounding("Great [1]. Wild [5].", {1}) == ["dangling citation [5]"]


def test_gate_blocks_uncited_claim_line() -> None:
    issues = enforce_grounding("Cited [1].\nNo source for this.", {1})
    assert issues == ["uncited claim: No source for this."]


def test_gate_blocks_citation_free_draft() -> None:
    issues = enforce_grounding("Everyone loves it.", {1})
    assert "answer has no citations" in issues


def test_gate_passes_fully_cited_draft() -> None:
    assert enforce_grounding("A [1].\nB [1][2].", {1, 2}) == []


def test_composer_discards_failing_draft_and_records_issues(monkeypatch) -> None:
    class BadLLM:
        available = True

        async def complete(self, system, user, *, ledger, max_tokens=None):
            return "Unsourced praise."

    monkeypatch.setattr("agents.composer.get_llm", lambda: BadLLM())
    result = asyncio.run(compose("q", None, [_hit()], CostLedger()))

    grounding = result.audit["grounding"]
    assert grounding["path"] == "extractive"
    assert grounding["issues"][0] == "llm draft blocked"
    assert "answer has no citations" in grounding["issues"]
    assert "battery dies fast [1]" in result.answer
