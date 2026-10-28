import asyncio

import pytest

from agents import pipeline
from app.config import Settings
from governance import audit
from governance.audit import AUDIT_TABLE, AuditStore


class NoLLM:
    available = False


@pytest.fixture
def store():
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml for the live audit test")
    store = AuditStore(url.get_secret_value())
    try:
        store.ensure_schema()
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {type(exc).__name__}")
    return store


def test_record_round_trips_an_audit_dict(store) -> None:
    marker = "audit-roundtrip-test"
    store.record(
        {
            "query": marker,
            "role": "support",
            "intent": "review_rag",
            "tool_path": ["review_rag"],
            "sources": ["c1", "c2"],
            "tokens": 12,
            "cost_usd": 0.5,
            "latency_ms": 3.5,
            "grounding": {"grounded": True},
        }
    )
    with store._connect() as conn:
        row = conn.execute(f"SELECT * FROM {AUDIT_TABLE} WHERE query = %s", [marker]).fetchone()
        conn.execute(f"DELETE FROM {AUDIT_TABLE} WHERE query = %s", [marker])
    assert row["role"] == "support" and row["intent"] == "review_rag"
    assert row["tool_path"] == ["review_rag"] and row["sources"] == ["c1", "c2"]
    assert row["tokens"] == 12 and row["cost_usd"] == 0.5 and row["latency_ms"] == 3.5
    assert row["grounding"] == {"grounded": True} and row["memory"] is None
    assert row["created_at"] is not None


def test_failing_audit_store_does_not_break_the_turn(monkeypatch) -> None:
    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())
    monkeypatch.setattr("agents.router.get_llm", lambda: NoLLM())
    monkeypatch.setattr(pipeline, "review_rag", lambda q, scope: [])

    def boom(_: dict) -> None:
        raise RuntimeError("audit db down")

    monkeypatch.setattr(pipeline, "record_audit", boom)
    monkeypatch.setattr(audit, "_schema_ready", False)

    result = asyncio.run(pipeline.answer("what do customers say about batteries?", "support"))

    assert result.answer and result.audit["role"] == "support"


def test_record_redacts_pii_in_the_stored_query(store) -> None:
    tag = "audit-pii-test"
    store.record(
        {"query": f"{tag} mail jane.doe@example.com or call +1 415-555-0132", "role": "support"}
    )
    with store._connect() as conn:
        row = conn.execute(
            f"SELECT query FROM {AUDIT_TABLE} WHERE query LIKE %s", [f"{tag}%"]
        ).fetchone()
        conn.execute(f"DELETE FROM {AUDIT_TABLE} WHERE query LIKE %s", [f"{tag}%"])
    assert row["query"].startswith(tag)
    assert "jane.doe@example.com" not in row["query"] and "415-555-0132" not in row["query"]
