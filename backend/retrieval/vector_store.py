from typing import Protocol

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from app.config import Settings, get_settings
from retrieval.embeddings import GoAheadRequired, get_embedder
from retrieval.schema import CHUNK_COLUMNS, CHUNKS_TABLE, Chunk, SearchHit, chunks_ddl

_META_COLUMNS = tuple(c for c in CHUNK_COLUMNS if c != "embedding")

# Columns a caller may filter on; the allowlist keeps the WHERE builder injection-proof.
FILTER_COLUMNS = ("source_type", "source", "category")

Filters = dict[str, str | list[str]]


def build_where(filters: Filters | None) -> tuple[str, list[object]]:
    """The single access choke point: all retrieval builds its WHERE here (M6 tightens it)."""
    clauses: list[str] = []
    params: list[object] = []
    for column, value in (filters or {}).items():
        if column not in FILTER_COLUMNS:
            raise ValueError(f"unsupported filter column: {column}")
        if isinstance(value, str):
            clauses.append(f"{column} = %s")
            params.append(value)
        else:
            clauses.append(f"{column} = ANY(%s)")
            params.append(list(value))
    return (f"WHERE {' AND '.join(clauses)} " if clauses else ""), params


def _to_hits(rows: list[tuple]) -> list[SearchHit]:
    return [
        SearchHit(
            chunk=Chunk(**dict(zip(_META_COLUMNS, row[:-1], strict=True))),
            score=row[-1],
        )
        for row in rows
    ]


class VectorStore(Protocol):
    def ensure_schema(self) -> None: ...

    def upsert(self, chunks: list[Chunk]) -> int: ...

    def query(
        self, vector: list[float], k: int, *, filters: Filters | None = None
    ) -> list[SearchHit]: ...

    def keyword_query(
        self, query: str, k: int, *, filters: Filters | None = None
    ) -> list[SearchHit]: ...


class PgVectorStore:
    """Postgres + pgvector; $0 local default. Connects per call (batch/CLI use, no pool)."""

    def __init__(self, database_url: str, dim: int) -> None:
        self._url = database_url
        self._dim = dim

    def _connect(self, *, vectors: bool = True) -> psycopg.Connection:
        conn = psycopg.connect(self._url)
        if vectors:
            register_vector(conn)
        return conn

    def ensure_schema(self) -> None:
        # The vector type must exist before register_vector can look it up.
        with self._connect(vectors=False) as conn:
            for statement in chunks_ddl(self._dim):
                conn.execute(statement)

    def upsert(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        cols = ", ".join(CHUNK_COLUMNS)
        marks = ", ".join(["%s"] * len(CHUNK_COLUMNS))
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in CHUNK_COLUMNS if c != "id")
        sql = (
            f"INSERT INTO {CHUNKS_TABLE} ({cols}) VALUES ({marks}) "
            f"ON CONFLICT (id) DO UPDATE SET {updates}"
        )
        rows = []
        for chunk in chunks:
            if chunk.embedding is None or len(chunk.embedding) != self._dim:
                raise ValueError(f"chunk {chunk.id} needs an embedding of dim {self._dim}")
            row = [getattr(chunk, c) for c in CHUNK_COLUMNS]
            row[CHUNK_COLUMNS.index("embedding")] = Vector(chunk.embedding)
            rows.append(row)
        with self._connect() as conn, conn.cursor() as cur:
            cur.executemany(sql, rows)
        return len(rows)

    def query(
        self, vector: list[float], k: int, *, filters: Filters | None = None
    ) -> list[SearchHit]:
        cols = ", ".join(_META_COLUMNS)
        where, params = build_where(filters)
        sql = (
            f"SELECT {cols}, 1 - (embedding <=> %s) AS score FROM {CHUNKS_TABLE} {where}"
            "ORDER BY embedding <=> %s, id LIMIT %s"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, [Vector(vector), *params, Vector(vector), k]).fetchall()
        return _to_hits(rows)

    def keyword_query(
        self, query: str, k: int, *, filters: Filters | None = None
    ) -> list[SearchHit]:
        cols = ", ".join(_META_COLUMNS)
        where, params = build_where(filters)
        match = "to_tsvector('english', text) @@ plainto_tsquery('english', %s)"
        where = f"{where}AND {match} " if where else f"WHERE {match} "
        sql = (
            f"SELECT {cols}, ts_rank(to_tsvector('english', text), "
            f"plainto_tsquery('english', %s)) AS score FROM {CHUNKS_TABLE} {where}"
            "ORDER BY score DESC, id LIMIT %s"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, [query, *params, query, k]).fetchall()
        return _to_hits(rows)


class AzureSearchStore:
    """Azure AI Search. Inert: provisioning costs money, so every call refuses."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _refuse(self) -> GoAheadRequired:
        return GoAheadRequired(
            "Azure AI Search store requires human go-ahead: provisioning and indexing are "
            "not enabled in this build. Use VECTOR_STORE=pgvector for $0 runs."
        )

    def ensure_schema(self) -> None:
        raise self._refuse()

    def upsert(self, chunks: list[Chunk]) -> int:
        raise self._refuse()

    def query(
        self, vector: list[float], k: int, *, filters: Filters | None = None
    ) -> list[SearchHit]:
        raise self._refuse()

    def keyword_query(
        self, query: str, k: int, *, filters: Filters | None = None
    ) -> list[SearchHit]:
        raise self._refuse()


def get_vector_store() -> VectorStore:
    settings = get_settings()
    if settings.vector_store == "azure_search":
        return AzureSearchStore(settings)
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not set; it is required for VECTOR_STORE=pgvector.")
    return PgVectorStore(settings.database_url.get_secret_value(), get_embedder().dim)
