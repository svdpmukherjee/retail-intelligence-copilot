import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from governance.audit import AUDIT_TABLE, AuditStore


@pytest.fixture
def store():
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set")
    s = AuditStore(url.get_secret_value())
    try:
        s.ensure_schema()
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {type(exc).__name__}")
    with s._connect() as c:
        assert c.execute("select current_database() d").fetchone()["d"].endswith("_test")
        c.execute(f"TRUNCATE {AUDIT_TABLE} RESTART IDENTITY")
    return s


def _seed(store, n=5):
    for i in range(n):
        store.record(
            {
                "query": f"q{i}",
                "role": "admin",
                "intent": "x",
                "tool_path": ["a"],
                "sources": [],
                "tokens": 10 + i,
                "cost_usd": 0.01,
                "latency_ms": 5.0,
            }
        )


def test_list_recent_order_pagination_get_count(store):
    _seed(store)
    rows = store.list_recent(limit=2, offset=0)
    assert [r["query"] for r in rows] == ["q4", "q3"]
    assert [r["query"] for r in store.list_recent(limit=2, offset=2)] == ["q2", "q1"]
    assert len(store.list_recent(limit=9999)) == 5
    assert len(store.list_recent(limit=0)) == 1
    assert store.list_recent(limit=2, offset=-5)[0]["query"] == "q4"
    assert store.count() == 5
    assert store.get(rows[0]["id"])["query"] == "q4"
    assert store.get(999999) is None


def test_endpoints_smoke(store):
    _seed(store, 3)
    c = TestClient(app)
    r = c.get("/audit", params={"role": "admin", "limit": 2})
    assert r.status_code == 200
    b = r.json()
    assert b["total"] == 3 and b["limit"] == 2 and b["offset"] == 0
    assert [i["query"] for i in b["items"]] == ["q2", "q1"]
    for k in ("id", "created_at", "tokens", "cost_usd", "latency_ms", "tool_path"):
        assert k in b["items"][0]
    assert c.get("/audit", params={"role": "support"}).status_code == 403
    assert c.get("/audit", params={"role": "nope"}).status_code == 400
    assert c.get("/audit", params={"role": "admin", "limit": 500}).status_code == 422
    assert c.get(f"/audit/{b['items'][0]['id']}", params={"role": "admin"}).status_code == 200
    assert c.get("/audit/999999", params={"role": "admin"}).status_code == 404
    assert c.get("/audit/1", params={"role": "support"}).status_code == 403
