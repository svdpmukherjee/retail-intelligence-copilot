from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.config import Settings
from memory.store import MemoryStore


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Iterator[MemoryStore]:
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run memory tests")
    s = MemoryStore(url.get_secret_value())
    try:
        s.ensure_schema()
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {type(exc).__name__}")
    monkeypatch.setattr(main, "get_memory_store", lambda: s)
    yield s
    with s._connect() as conn:
        conn.execute("DROP TABLE messages, threads, user_memory")


def _seed(store: MemoryStore, user: str, role: str, first: str) -> str:
    thread = store.create_thread(user, role)
    store.append_message(thread.id, "user", first, user_id=user)
    store.append_message(thread.id, "assistant", "an answer", user_id=user)
    return thread.id


def test_threads_are_isolated_per_owner(store: MemoryStore) -> None:
    mine = _seed(store, "support_1", "support", "my question")
    _seed(store, "support_2", "support", "their question")
    body = TestClient(main.app).get("/threads", params={"user_id": "support_1", "role": "support"})
    assert [t["id"] for t in body.json()["threads"]] == [mine]


def test_thread_not_listed_under_another_role(store: MemoryStore) -> None:
    _seed(store, "alice", "support", "q")
    r = TestClient(main.app).get("/threads", params={"user_id": "alice", "role": "executive"})
    assert r.status_code == 200 and r.json() == {"threads": []}


def test_label_and_turn_count_are_server_derived(store: MemoryStore) -> None:
    _seed(store, "alice", "support", "x" * 80)
    row = (
        TestClient(main.app)
        .get("/threads", params={"user_id": "alice", "role": "support"})
        .json()["threads"][0]
    )
    assert set(row) == {"id", "label", "created_at", "turn_count"}
    assert row["label"] == "x" * 48 and row["turn_count"] == 2


def test_non_owner_thread_detail_returns_no_content(store: MemoryStore) -> None:
    tid = _seed(store, "support_1", "support", "secret")
    client = TestClient(main.app)
    foreign = client.get(f"/threads/{tid}", params={"user_id": "support_2"})
    assert foreign.status_code == 404 and "secret" not in foreign.text
    own = client.get(f"/threads/{tid}", params={"user_id": "support_1"}).json()
    assert [t["turn"] for t in own["turns"]] == [1, 2] and own["role"] == "support"


def test_unknown_role_is_a_clean_400() -> None:
    r = TestClient(main.app).get("/threads", params={"user_id": "a", "role": "nope"})
    assert r.status_code == 400
