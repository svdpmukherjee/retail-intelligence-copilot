import asyncio
from collections.abc import Iterator

import pytest

from agents import composer, router
from agents.composer import AnswerResult, Citation
from app.config import Settings
from app.cost import CostLedger
from memory.manager import MemoryContext, MemoryManager, Turn
from memory.store import MemoryStore
from retrieval.schema import Chunk, SearchHit


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


class FakeLLM:
    available = True

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.users: list[str] = []

    async def complete(self, system, user, *, ledger, max_tokens=None):
        self.users.append(user)
        return self.reply


class NoLLM:
    available = False


def _ctx() -> MemoryContext:
    return MemoryContext(
        thread_id="t1",
        history=[Turn(role_kind="user", content="tell me about the X100 battery")],
        preferences=["prefers short answers"],
    )


def _hit() -> SearchHit:
    chunk = Chunk(id="c1", source_type="review", text="battery dies fast", asin="B01", category="E")
    return SearchHit(chunk=chunk, score=1.0)


def test_load_empty_thread_gives_empty_context(store: MemoryStore) -> None:
    ctx = MemoryManager(store).load("nope", "alice", "analyst", limit=6)
    assert ctx.history == [] and ctx.preferences == [] and ctx.prior_findings == []
    assert ctx.render() == ""


def test_load_seeded_thread_is_bounded_and_owner_scoped(store: MemoryStore) -> None:
    thread = store.create_thread("alice", "analyst")
    for i in range(10):
        store.append_message(
            thread.id, "user" if i % 2 == 0 else "assistant", f"m{i}", user_id="alice"
        )
    store.add_memory("alice", "preference", "likes bullets", {})
    store.add_memory("alice", "finding", "battery complaints rose", {})
    manager = MemoryManager(store)

    ctx = manager.load(thread.id, "alice", "analyst", limit=4)
    assert [t.content for t in ctx.history] == ["m6", "m7", "m8", "m9"]
    assert ctx.preferences == ["likes bullets"]
    assert ctx.prior_findings == ["battery complaints rose"]
    assert (
        len(manager.load(thread.id, "alice", "analyst", limit=99).history) == 6
    )  # memory_history_turns
    assert manager.load(thread.id, "mallory", "analyst", limit=6).history == []


def test_render_is_capped_to_history_turns() -> None:
    history = [Turn(role_kind="user", content=f"q{i}") for i in range(20)]
    text = MemoryContext(thread_id="t", history=history).render()
    assert "q19" in text and "q13" not in text and text.count("user:") == 6


def test_route_context_none_is_unchanged_and_context_reaches_llm(monkeypatch) -> None:
    llm = FakeLLM('{"intent": "docs_rag", "rationale": "r"}')
    monkeypatch.setattr("agents.router.get_llm", lambda: llm)

    asyncio.run(router.route("returns policy?", "analyst"))
    asyncio.run(router.route("returns policy?", "analyst", context=_ctx()))

    assert llm.users[0] == "returns policy?"
    assert llm.users[1].startswith(_ctx().render())
    assert llm.users[1].endswith("Question: returns policy?")

    monkeypatch.setattr("agents.router.get_llm", lambda: NoLLM())
    plain = asyncio.run(router.route("average rating?", "analyst"))
    with_ctx = asyncio.run(router.route("average rating?", "analyst", context=_ctx()))
    assert plain == with_ctx


def test_compose_context_reaches_llm_but_is_never_cited(monkeypatch) -> None:
    llm = FakeLLM("Batteries die fast [1].")
    monkeypatch.setattr("agents.composer.get_llm", lambda: llm)

    plain = asyncio.run(composer.compose("q", None, [_hit()], CostLedger()))
    with_ctx = asyncio.run(composer.compose("q", None, [_hit()], CostLedger(), context=_ctx()))

    assert llm.users[0] == "Question: q\n\nSources:\n[1] (review B01 (E)) battery dies fast"
    assert llm.users[1].startswith(_ctx().render())
    assert llm.users[1].endswith(llm.users[0])
    assert plain == with_ctx
    assert [c.source_id for c in with_ctx.citations] == ["c1"]


def test_compose_extractive_ignores_context(monkeypatch) -> None:
    monkeypatch.setattr("agents.composer.get_llm", lambda: NoLLM())
    plain = asyncio.run(composer.compose("q", None, [_hit()], CostLedger()))
    with_ctx = asyncio.run(composer.compose("q", None, [_hit()], CostLedger(), context=_ctx()))
    assert plain == with_ctx


def _result(answer: str = "Batteries die fast [1]. Returns are free [2].") -> AnswerResult:
    return AnswerResult(
        answer=answer,
        citations=[Citation(n=1, source_id="c1", label="review B01 (E)")],
        audit={"intent": "review_rag", "sources": ["c1"]},
    )


def test_persist_appends_two_messages_and_one_finding_at_zero_cost(
    store: MemoryStore, monkeypatch
) -> None:
    monkeypatch.setattr("memory.manager.get_llm", lambda: NoLLM())
    thread = store.create_thread("alice", "analyst")
    ledger = CostLedger()

    count = asyncio.run(
        MemoryManager(store).persist(
            thread.id, "alice", "analyst", "battery?", _result(), ledger, scope={"category": "E"}
        )
    )

    assert count == 1
    assert [m.role_kind for m in store.recent_messages(thread.id, 10)] == ["user", "assistant"]
    findings = store.list_memory("alice", kind="finding", limit=10)
    assert len(findings) == 1
    assert findings[0].content.startswith("Batteries die fast. Returns are free.")
    assert "review_rag" in findings[0].content and "c1" in findings[0].content
    assert findings[0].scope == {"category": "E"}
    assert ledger.tokens == 0 and ledger.usd == 0.0


def test_persist_redacts_pii_and_stores_preference(store: MemoryStore, monkeypatch) -> None:
    monkeypatch.setattr("memory.manager.get_llm", lambda: NoLLM())
    thread = store.create_thread("alice", "analyst")
    answer = "Contact bob@example.com or 555-123-4567 for refunds [1]."

    asyncio.run(
        MemoryManager(store).persist(
            thread.id,
            "alice",
            "analyst",
            "I prefer bullet points. mail me at a@b.io",
            _result(answer),
            CostLedger(),
            scope={},
        )
    )

    stored = [m.content for m in store.recent_messages(thread.id, 10)]
    stored += [r.content for r in store.list_memory("alice", limit=10)]
    joined = " ".join(stored)
    assert "bob@example.com" not in joined and "555-123-4567" not in joined
    assert "a@b.io" not in joined and "[EMAIL]" in joined and "[PHONE]" in joined
    assert [r.content for r in store.list_memory("alice", kind="preference", limit=5)] == [
        "I prefer bullet points"
    ]


def test_persist_uses_llm_summary_through_ledger_when_available(
    store: MemoryStore, monkeypatch
) -> None:
    llm = FakeLLM("LLM summary.")
    monkeypatch.setattr("memory.manager.get_llm", lambda: llm)
    thread = store.create_thread("alice", "analyst")

    asyncio.run(
        MemoryManager(store).persist(
            thread.id, "alice", "analyst", "q", _result(), CostLedger(), scope={}
        )
    )

    assert store.list_memory("alice", kind="finding", limit=1)[0].content.startswith("LLM summary.")


def test_persist_trims_oldest_beyond_memory_max_items(store: MemoryStore, monkeypatch) -> None:
    monkeypatch.setattr("memory.manager.get_llm", lambda: NoLLM())
    monkeypatch.setenv("MEMORY_MAX_ITEMS", "3")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        thread = store.create_thread("alice", "analyst")
        manager = MemoryManager(store)
        for i in range(5):
            asyncio.run(
                manager.persist(
                    thread.id,
                    "alice",
                    "analyst",
                    "q",
                    _result(f"Answer {i} [1]."),
                    CostLedger(),
                    scope={},
                )
            )
        kept = [r.content for r in store.list_memory("alice", limit=10)]
        assert len(kept) == 3
        assert kept[0].startswith("Answer 4") and kept[-1].startswith("Answer 2")
    finally:
        get_settings.cache_clear()
