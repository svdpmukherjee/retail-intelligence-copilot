from collections.abc import Iterator

import pytest

from app.config import Settings
from memory.store import MemoryStore


@pytest.fixture
def store() -> Iterator[MemoryStore]:
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run memory tests")
    s = MemoryStore(url.get_secret_value())
    try:
        s.ensure_schema()
    except Exception as exc:
        pytest.skip(f"Postgres not reachable: {type(exc).__name__}")
    yield s
    with s._connect() as conn:
        conn.execute("DROP TABLE messages, threads, user_memory")


def test_recent_messages_are_capped_newest_n_oldest_first(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    for i in range(5):
        store.append_message(
            thread.id, "user" if i % 2 == 0 else "assistant", f"m{i}", user_id="alice"
        )
    rows = store.recent_messages(thread.id, 3)
    assert [r.content for r in rows] == ["m2", "m3", "m4"]
    assert [r.turn for r in rows] == [3, 4, 5]
    assert rows[0].role_kind == "user" and rows[1].role_kind == "assistant"


def test_recent_messages_enforces_thread_ownership(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    store.append_message(thread.id, "user", "hi", user_id="alice")
    assert len(store.recent_messages(thread.id, 5, user_id="alice")) == 1
    assert store.recent_messages(thread.id, 5, user_id="bob") == []
    assert store.recent_messages("unknown", 5) == []


def test_list_memory_is_filtered_by_user_and_kind(store: MemoryStore) -> None:
    store.add_memory("alice", "preference", "likes short answers", {})
    store.add_memory("alice", "finding", "battery complaints rose", {"source": ["review"]})
    assert [m.kind for m in store.list_memory("alice", limit=10)] == ["finding", "preference"]
    findings = store.list_memory("alice", kind="finding", limit=10)
    assert [m.content for m in findings] == ["battery complaints rose"]
    assert findings[0].scope == {"source": ["review"]}
    assert store.list_memory("bob", limit=10) == []
    assert len(store.list_memory("alice", limit=1)) == 1
