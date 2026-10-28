import asyncio
from collections.abc import Iterator

import pytest

from agents.composer import AnswerResult
from app.config import Settings
from app.cost import CostLedger
from governance.policy import AccessDenied
from memory.manager import MemoryManager
from memory.store import MemoryStore

SUPPORT_OK = {"category": ["Electronics"]}
MARKETING_ONLY = {"category": ["Books"]}


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


def _seed(store: MemoryStore) -> None:
    store.add_memory("alice", "finding", "electronics finding", SUPPORT_OK)
    store.add_memory("alice", "finding", "books finding", MARKETING_ONLY)
    store.add_memory("alice", "finding", "mixed finding", {"category": ["Electronics", "Books"]})
    store.add_memory("alice", "finding", "unscoped finding", {})
    store.add_memory("alice", "preference", "likes bullets", MARKETING_ONLY)


def test_list_memory_scope_filter_runs_in_the_query(store: MemoryStore) -> None:
    _seed(store)
    support = {"category": ["Electronics", "Home_and_Kitchen"]}
    rows = store.list_memory("alice", kind="finding", limit=10, scope=support)
    assert [r.content for r in rows] == ["electronics finding"]
    # limit applies after filtering: a SQL filter still fills the page, a Python one would not
    assert len(store.list_memory("alice", kind="finding", limit=1, scope=support)) == 1
    assert len(store.list_memory("alice", kind="finding", limit=10, scope={})) == 4


def test_manager_load_hides_out_of_scope_findings_for_scoped_role(store: MemoryStore) -> None:
    _seed(store)
    manager = MemoryManager(store)
    thread = store.create_thread("alice", "support")
    support = manager.load(thread.id, "alice", "support", limit=6)
    assert support.prior_findings == ["electronics finding"]
    assert support.preferences == ["likes bullets"]
    marketing = manager.load(thread.id, "alice", "marketing", limit=6)
    assert marketing.prior_findings == ["books finding"]
    full = manager.load(thread.id, "alice", "executive", limit=6)
    assert len(full.prior_findings) == 4


def test_manager_load_denies_unknown_role(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    with pytest.raises(AccessDenied):
        MemoryManager(store).load(thread.id, "alice", "intruder", limit=6)


def test_append_message_by_non_owner_raises_and_persists_nothing(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    store.append_message(thread.id, "user", "hi", user_id="alice")
    with pytest.raises(PermissionError):
        store.append_message(thread.id, "user", "evil", user_id="mallory")
    with pytest.raises(PermissionError):
        store.append_message("unknown", "user", "x", user_id="alice")
    assert [m.content for m in store.recent_messages(thread.id, 10)] == ["hi"]


def test_append_message_to_empty_owned_thread_starts_at_turn_one(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    assert store.append_message(thread.id, "user", "first", user_id="alice").turn == 1


def test_persist_by_non_owner_writes_nothing(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    result = AnswerResult(answer="Battery is poor [1].", citations=[], audit={})
    with pytest.raises(PermissionError):
        asyncio.run(
            MemoryManager(store).persist(
                thread.id, "mallory", "analyst", "q", result, CostLedger(), scope={}
            )
        )
    assert store.recent_messages(thread.id, 10) == []
    assert store.list_memory("mallory", limit=10) == []
