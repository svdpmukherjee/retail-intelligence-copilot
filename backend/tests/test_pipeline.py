import asyncio

import pytest
from fastapi.testclient import TestClient

from agents import pipeline
from agents.router import RouteDecision
from app.config import Settings
from app.main import app
from retrieval.index_reviews import index_reviews, read_gold_reviews
from retrieval.schema import Chunk, SearchHit
from retrieval.vector_store import get_vector_store

client = TestClient(app)


class NoLLM:
    available = False


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())


def _route(intent):
    async def fake(query, role, ledger=None):
        return RouteDecision(intent=intent, scope={}, rationale="test")

    return fake


def test_query_returns_answer_with_audit(monkeypatch) -> None:
    hit = SearchHit(
        chunk=Chunk(id="c1", source_type="review", text="battery dies", asin="B1", category="E"),
        score=1.0,
    )
    monkeypatch.setattr(pipeline, "route", _route("review_rag"))
    monkeypatch.setattr(pipeline, "review_rag", lambda q, scope: [hit])

    resp = client.post("/query", json={"query": "complaints?", "role": "support"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"][0]["source_id"] == "c1"
    audit = body["audit"]
    assert audit["role"] == "support" and audit["intent"] == "review_rag"
    assert audit["sources"] == ["c1"] and audit["tool_path"] == ["review_rag"]
    assert audit["cost_usd"] == 0.0 and "tokens" in audit


def test_sql_tool_failure_becomes_clean_http_error(monkeypatch) -> None:
    async def boom(query, scope, ledger):
        raise RuntimeError("Catalog Error: no such column")

    monkeypatch.setattr(pipeline, "route", _route("sql"))
    monkeypatch.setattr(pipeline, "sql_agent", boom)

    resp = client.post("/query", json={"query": "how many?", "role": "support"})

    assert resp.status_code == 502
    assert "Catalog Error" in resp.json()["detail"]


@pytest.fixture
def seeded_store():
    if Settings().database_url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml for the live e2e smoke")
    store = get_vector_store()
    try:
        with store._connect(vectors=False) as conn:
            conn.execute("DROP TABLE IF EXISTS chunks")
        store.ensure_schema()
    except Exception as exc:
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    yield store
    with store._connect(vectors=False) as conn:
        conn.execute("DROP TABLE chunks")


def test_end_to_end_free_mode_grounded_cited_answer(seeded_store, monkeypatch) -> None:
    monkeypatch.setattr("agents.router.get_llm", lambda: NoLLM())
    index_reviews()
    category = read_gold_reviews(1)[0]["category"]

    result = asyncio.run(
        pipeline.answer(f"what are common complaints about {category}?", "executive")
    )

    assert result.citations
    ids = set(result.audit["sources"])
    assert {c.source_id for c in result.citations} <= ids
    assert result.audit["tool_path"] == ["review_rag"]
    assert result.audit["cost_usd"] == 0.0
    assert result.audit["grounding"]["issues"] == []
