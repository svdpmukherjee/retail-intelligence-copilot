import asyncio

import pytest

from agents.composer import compose
from app.cost import CostLedger
from governance.pii import redact
from retrieval.schema import Chunk, SearchHit

PHONES = [
    "(555) 123-4567",
    "555-123-4567",
    "+1 555 123 4567",
    "555-0142",
    "+44 20 7946 0958",
    "+44 (0)20 7946 0958",
    "+447911123456",
    "020 7946 0958",
    "07911 123456",
    "01632 960 001",
    "+49 30 901820",
    "+33 1 42 68 53 00",
    "+91 98765 43210",
]
SURVIVORS = ["2024", "order #48213", "$1,299.99", "rated 4.5 stars", "1999-2004", "12345", "0.99"]


@pytest.mark.parametrize("phone", PHONES)
def test_phone_forms_are_redacted(phone: str) -> None:
    out = redact(f"call me on {phone} please")
    assert out == "call me on [PHONE] please"


def test_email_is_redacted() -> None:
    assert redact("mail jane.doe+x@example.co.uk now") == "mail [EMAIL] now"


@pytest.mark.parametrize("text", SURVIVORS)
def test_non_phone_digits_survive(text: str) -> None:
    assert redact(f"bought in {text} ok") == f"bought in {text} ok"


def test_citation_markers_are_preserved() -> None:
    assert redact("Good battery [1] and loud [12].") == "Good battery [1] and loud [12]."


class _Chunky:
    available = True

    async def complete(self, system, user, *, ledger, max_tokens=None):
        return "Reach support at help@shop.com or +44 20 7946 0958 [1]."


def test_llm_draft_pii_is_scrubbed_from_served_answer(monkeypatch) -> None:
    monkeypatch.setattr("agents.composer.get_llm", lambda: _Chunky())
    chunk = Chunk(id="c1", source_type="review", text="battery", asin="B01", category="E")
    result = asyncio.run(compose("q", None, [SearchHit(chunk=chunk, score=1.0)], CostLedger()))

    assert result.audit["grounding"]["path"] == "llm"
    assert result.answer == "Reach support at [EMAIL] or [PHONE] [1]."
    assert [c.n for c in result.citations] == [1]


def test_extractive_answer_pii_is_scrubbed(monkeypatch) -> None:
    class NoLLM:
        available = False

    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())
    chunk = Chunk(id="c1", source_type="review", text="call 555-123-4567", asin="B01", category="E")
    result = asyncio.run(compose("q", None, [SearchHit(chunk=chunk, score=1.0)], CostLedger()))

    assert "555-123-4567" not in result.answer
    assert "[PHONE]" in result.answer
