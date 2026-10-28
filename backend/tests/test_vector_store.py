from collections.abc import Iterator

import pytest
from pydantic import SecretStr

from app.config import Settings
from retrieval import vector_store
from retrieval.embeddings import GoAheadRequired
from retrieval.schema import Chunk, make_chunk_id
from retrieval.vector_store import AzureSearchStore, PgVectorStore, get_vector_store

DIM = 3


def _chunk(key: str, vec: list[float], **kw: object) -> Chunk:
    return Chunk(id=make_chunk_id(key), source_type="review", text=key, embedding=vec, **kw)


@pytest.fixture
def store() -> Iterator[PgVectorStore]:
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    s = PgVectorStore(url.get_secret_value(), DIM)
    try:
        # Vector dim is fixed at table creation; drop so a leftover table of another dim can't leak.
        with s._connect(vectors=False) as conn:
            conn.execute("DROP TABLE IF EXISTS chunks")
        s.ensure_schema()
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    yield s
    with s._connect(vectors=False) as conn:
        conn.execute("DROP TABLE chunks")


def test_upsert_then_query_returns_nearest_and_is_idempotent(
    store: PgVectorStore,
) -> None:
    chunks = [
        _chunk("a", [1.0, 0.0, 0.0], category="Books", year=2021, asin="A1"),
        _chunk("b", [0.0, 1.0, 0.0]),
        _chunk("c", [0.0, 0.0, 1.0]),
    ]
    store.upsert(chunks)
    store.upsert(chunks)
    hits = store.query([0.9, 0.1, 0.0], k=2)
    assert [h.chunk.text for h in hits] == ["a", "b"]
    assert hits[0].chunk.category == "Books" and hits[0].chunk.year == 2021
    assert hits[0].score > hits[1].score
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 3


def test_upsert_rejects_wrong_dimension(store: PgVectorStore) -> None:
    with pytest.raises(ValueError, match="dim 3"):
        store.upsert([_chunk("x", [1.0, 0.0])])


def test_azure_search_store_refuses_without_go_ahead() -> None:
    azure = AzureSearchStore(Settings(_env_file=None))
    with pytest.raises(GoAheadRequired, match="human go-ahead"):
        azure.ensure_schema()
    with pytest.raises(GoAheadRequired, match="human go-ahead"):
        azure.query([0.0], 1)


def test_factory_selects_store_by_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    def use(**kw: object) -> None:
        monkeypatch.setattr(vector_store, "get_settings", lambda: Settings(_env_file=None, **kw))

    use(vector_store="azure_search")
    assert isinstance(get_vector_store(), AzureSearchStore)
    use(vector_store="pgvector", database_url=SecretStr("postgresql://x"))
    monkeypatch.setattr(vector_store, "get_embedder", lambda: type("E", (), {"dim": DIM})())
    assert isinstance(get_vector_store(), PgVectorStore)


def test_chunk_ids_are_deterministic() -> None:
    assert make_chunk_id("A1", "t") == make_chunk_id("A1", "t") != make_chunk_id("A1", "u")
