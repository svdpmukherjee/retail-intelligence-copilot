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


def test_delete_thread_is_owner_scoped_and_removes_messages(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    store.append_message(thread.id, "user", "hi", user_id="alice")
    # A non-owner cannot delete it, and the thread survives.
    assert store.delete_thread(thread.id, "mallory") is False
    assert store.get_thread(thread.id, "alice") is not None
    # The owner can; the thread and its messages are gone.
    assert store.delete_thread(thread.id, "alice") is True
    assert store.get_thread(thread.id, "alice") is None
    assert store.recent_messages(thread.id, 10) == []
    # Deleting an already-gone thread is a no-op, not an error.
    assert store.delete_thread(thread.id, "alice") is False


def test_delete_all_threads_clears_only_this_user_and_role(store: MemoryStore) -> None:
    keep_a = store.create_thread("alice", "analyst")
    keep_b = store.create_thread("alice", "marketing")  # different role: must survive
    other = store.create_thread("bob", "analyst")  # different user: must survive
    for t, u in ((keep_a, "alice"), (keep_b, "alice"), (other, "bob")):
        store.append_message(t.id, "user", "hi", user_id=u)
    assert store.delete_all_threads("alice", "analyst") == 1
    assert store.get_thread(keep_a.id, "alice") is None
    assert store.get_thread(keep_b.id, "alice") is not None
    assert store.get_thread(other.id, "bob") is not None
    assert store.delete_all_threads("alice", "analyst") == 0  # nothing left under that role


def test_assistant_payload_round_trips_for_replay(store: MemoryStore) -> None:
    """An assistant turn's render snapshot survives a write/read so the chat replays in full."""
    thread = store.create_thread("alice", "analyst")
    snapshot = {
        "answer": "Batteries draw the most complaints [1]",
        "citations": [{"n": 1, "source_id": "c1"}],
        "sql": {"columns": ["category", "n"], "rows": [["battery", 42]], "total_rows": 1},
        "audit": {"role": "analyst", "sources": ["sql", "c1"]},
    }
    store.append_message(thread.id, "user", "what do customers complain about?", user_id="alice")
    store.append_message(thread.id, "assistant", "redacted text", user_id="alice", payload=snapshot)
    rows = store.recent_messages(thread.id, 5, user_id="alice")
    assert rows[0].payload is None  # user turn carries no snapshot
    assert rows[1].payload == snapshot  # assistant snapshot round-trips verbatim
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
