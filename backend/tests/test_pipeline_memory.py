import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import pipeline
from app.config import Settings
from app.main import app
from memory.manager import MemoryContext, Turn, effective_query
from memory.store import MemoryStore
from retrieval.index_docs import index_docs
from retrieval.index_reviews import index_reviews, read_gold_reviews
from retrieval.schema import Chunk, SearchHit
from retrieval.vector_store import get_vector_store

client = TestClient(app)
POLICY_DOC = Path(__file__).resolve().parents[2] / "data/docs/authored/return-refund-policy.md"


class NoLLM:
    available = False


def _stub_retrieval(monkeypatch) -> None:
    hit = SearchHit(
        chunk=Chunk(id="c1", source_type="review", text="battery dies", asin="B1", category="E"),
        score=1.0,
    )
    monkeypatch.setattr(pipeline, "review_rag", lambda q, scope: [hit])


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())
    monkeypatch.setattr("agents.router.get_llm", lambda: NoLLM())
    monkeypatch.setattr("memory.manager.get_llm", lambda: NoLLM())


@pytest.fixture
def live_db():
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml for the live smoke")
    vectors = get_vector_store()
    memory = MemoryStore(url.get_secret_value())
    try:
        with vectors._connect(vectors=False) as conn:
            conn.execute("DROP TABLE IF EXISTS chunks")
        vectors.ensure_schema()
        with memory._connect() as conn:
            conn.execute("DROP TABLE IF EXISTS messages, threads, user_memory")
    except Exception as exc:
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    pipeline._schema_ready = False
    index_reviews()
    yield memory
    pipeline._schema_ready = False
    with vectors._connect(vectors=False) as conn:
        conn.execute("DROP TABLE chunks")
    with memory._connect() as conn:
        conn.execute("DROP TABLE messages, threads, user_memory")


def test_two_turn_thread_loads_turn_one_and_persists_at_zero_cost(live_db) -> None:
    category = read_gold_reviews(1)[0]["category"]
    query = f"what are common complaints about {category}?"

    async def two_turns():
        first = await pipeline.answer(query, "support", thread_id=thread_id, user_id="alice")
        second = await pipeline.answer(query, "support", thread_id=thread_id, user_id="alice")
        return first, second

    thread_id = pipeline.new_thread("alice", "support")
    first, second = asyncio.run(two_turns())

    assert first.citations and first.audit["memory"] == {
        "thread_id": thread_id,
        "history_turns_used": 0,
        "persisted": 1,
        "followup_augmented": False,
    }
    assert second.audit["memory"]["history_turns_used"] == 2
    assert second.audit["memory"]["persisted"] == 1
    assert second.citations and second.audit["grounding"]["issues"] == []
    assert first.audit["cost_usd"] == second.audit["cost_usd"] == 0.0
    items = live_db.list_memory("alice", kind="finding", limit=10)
    assert len(items) == 2 and "sources" in items[0].content
    assert live_db.list_memory("bob", limit=10) == []


def test_query_endpoint_creates_thread_and_returns_ids(live_db) -> None:
    category = read_gold_reviews(1)[0]["category"]
    body = {"query": f"complaints about {category}?", "role": "support", "user_id": "alice"}

    first = client.post("/query", json=body)
    assert first.status_code == 200
    thread_id = first.json()["thread_id"]
    assert thread_id and first.json()["user_id"] == "alice"

    second = client.post("/query", json={**body, "thread_id": thread_id})
    assert second.json()["thread_id"] == thread_id
    assert second.json()["audit"]["memory"]["history_turns_used"] == 2


def test_memory_failure_degrades_to_plain_answer(monkeypatch) -> None:
    def down():
        raise RuntimeError("db down")

    monkeypatch.setattr(pipeline, "get_memory_store", down)
    pipeline._schema_ready = False
    _stub_retrieval(monkeypatch)
    result = asyncio.run(pipeline.answer("hello?", "support", thread_id="t", user_id="u"))

    assert result.audit["memory"]["error"].startswith("load: RuntimeError")
    assert result.audit["memory"]["persisted"] == 0
    assert result.answer


def test_without_ids_there_is_no_memory_block(monkeypatch) -> None:
    def forbidden():
        raise AssertionError("memory must not be touched")

    monkeypatch.setattr(pipeline, "get_memory_store", forbidden)
    _stub_retrieval(monkeypatch)
    for kwargs in ({}, {"thread_id": "t"}, {"user_id": "u"}):
        result = asyncio.run(pipeline.answer("hello?", "support", **kwargs))
        assert "memory" not in result.audit


def _context(*turns: tuple[str, str]) -> MemoryContext:
    return MemoryContext(thread_id="t", history=[Turn(role_kind=r, content=c) for r, c in turns])


def test_effective_query_augments_vague_followup_with_last_user_turn() -> None:
    context = _context(
        ("user", "what is the return policy?"),
        ("assistant", "Returns are accepted within 30 days."),
    )
    assert "return policy" in effective_query("why?", context)
    assert effective_query("why?", context).endswith("why?")
    cue = effective_query("what about opened items for gadgets today?", context)
    assert cue.startswith("what is the return policy?")


def test_effective_query_leaves_non_vague_or_history_free_query_unchanged() -> None:
    context = _context(("user", "what is the return policy?"), ("assistant", "30 days."))
    long_query = "which products get the most battery complaints this year"
    assert effective_query(long_query, context) == long_query
    assert effective_query("why?", _context()) == "why?"
    assert effective_query("why?", _context(("assistant", "hello"))) == "why?"


def test_vague_followup_after_policy_question_retrieves_policy_docs(live_db, tmp_path) -> None:
    (tmp_path / "return-refund-policy.md").write_text(POLICY_DOC.read_text(encoding="utf-8"))
    index_docs(tmp_path)

    async def two_turns():
        first = await pipeline.answer(
            "what is the return policy?", "support", thread_id=thread_id, user_id="alice"
        )
        second = await pipeline.answer("why?", "support", thread_id=thread_id, user_id="alice")
        return first, second

    thread_id = pipeline.new_thread("alice", "support")
    first, second = asyncio.run(two_turns())

    assert first.audit["memory"]["followup_augmented"] is False
    assert second.audit["memory"]["followup_augmented"] is True
    assert second.audit["query"] == "why?"
    assert second.audit["intent"] == "docs_rag"
    assert second.citations and second.audit["cost_usd"] == 0.0
    assert not any(c.label.startswith("review ") for c in second.citations)
