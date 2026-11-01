from collections.abc import Iterator

import pytest
from pgvector import Vector
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


class _RecordingConn:
    """Stands in for a psycopg connection; records the SQL/params query() sends."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[object]]] = []

    def __enter__(self) -> "_RecordingConn":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, sql: str, params: list[object]) -> "_RecordingConn":
        self.calls.append((sql, params))
        return self

    def fetchall(self) -> list[tuple]:
        return []


def test_query_sql_orders_by_distance_only_inside_ann_subquery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _RecordingConn()
    s = PgVectorStore("postgresql://unused", DIM)
    monkeypatch.setattr(s, "_connect", lambda **_: conn)
    s.query([1.0, 0.0, 0.0], 5, filters={"category": "Books"})
    sql, params = conn.calls[0]
    inner = sql[sql.index("(SELECT") + 1 : sql.index(") ann")]
    # HNSW needs a bare distance ORDER BY; the id tiebreaker must live in the outer query.
    assert "ORDER BY embedding <=> %s LIMIT %s" in inner and ", id" not in inner
    assert "WHERE category = %s" in inner
    assert sql.endswith("ann ORDER BY score DESC, id")
    assert [type(p).__name__ for p in params] == ["Vector", "str", "Vector", "int"]
    assert params[-1] == 5


def test_query_breaks_score_ties_by_id_and_respects_filters_and_k(store: PgVectorStore) -> None:
    same = [1.0, 0.0, 0.0]
    chunks = [
        _chunk("t1", same, category="Books"),
        _chunk("t2", same, category="Books"),
        _chunk("t3", same, category="Toys"),
        _chunk("far", [0.0, 1.0, 0.0], category="Books"),
    ]
    store.upsert(chunks)
    hits = store.query(same, k=3)
    ids = [h.chunk.id for h in hits]
    tied = sorted(c.id for c in chunks[:3])
    assert ids == tied
    assert len(store.query(same, k=2)) == 2
    books = store.query(same, k=10, filters={"category": "Books"})
    assert {h.chunk.category for h in books} == {"Books"} and len(books) == 3


def test_query_plan_uses_hnsw_index(store: PgVectorStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.upsert([_chunk(f"p{i}", [1.0, float(i), 0.0]) for i in range(20)])
    real = store._connect()
    seen: list[str] = []

    class _Spy:
        def __enter__(self) -> "_Spy":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def execute(self, sql: str, params: list[object]) -> "_Spy":
            seen.append(sql)
            self._rows: list[tuple] = []
            return self

        def fetchall(self) -> list[tuple]:
            return self._rows

    monkeypatch.setattr(store, "_connect", lambda **_: _Spy())
    store.query([1.0, 0.0, 0.0], 3)
    # A 20-row table makes the planner prefer a seq scan; disable it to test plan *shape*.
    with real as conn:
        conn.execute("SET enable_seqscan = off")
        plan = conn.execute(
            "EXPLAIN (FORMAT JSON) " + seen[0], [Vector([1.0, 0.0, 0.0])] * 2 + [3]
        ).fetchone()[0]
    text = str(plan)
    assert "chunks_embedding_hnsw_idx" in text and "Seq Scan" not in text
