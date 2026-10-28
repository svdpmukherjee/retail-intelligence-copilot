import hashlib
from typing import Literal

from pydantic import BaseModel

CHUNKS_TABLE = "chunks"

# Columns M4 reads, in order. `source` is the hook M6 access policy filters on at retrieval.
CHUNK_COLUMNS = (
    "id",
    "source_type",
    "text",
    "embedding",
    "category",
    "asin",
    "year",
    "doc_id",
    "doc_title",
    "section",
    "chunk_index",
    "source",
)


class Chunk(BaseModel):
    id: str
    source_type: Literal["review", "doc"]
    text: str
    embedding: list[float] | None = None
    category: str | None = None
    asin: str | None = None
    year: int | None = None
    doc_id: str | None = None
    doc_title: str | None = None
    section: str | None = None
    chunk_index: int | None = None
    source: str | None = None


class SearchHit(BaseModel):
    chunk: Chunk
    score: float  # cosine similarity, higher is closer


def make_chunk_id(*keys: object) -> str:
    """Deterministic id from source keys, so re-indexing upserts rather than duplicates."""
    return hashlib.sha1("\x1f".join(str(k) for k in keys).encode()).hexdigest()


def chunks_ddl(dim: int) -> list[str]:
    return [
        "CREATE EXTENSION IF NOT EXISTS vector",
        f"""CREATE TABLE IF NOT EXISTS {CHUNKS_TABLE} (
            id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL CHECK (source_type IN ('review', 'doc')),
            text TEXT NOT NULL,
            embedding vector({int(dim)}) NOT NULL,
            category TEXT,
            asin TEXT,
            year INTEGER,
            doc_id TEXT,
            doc_title TEXT,
            section TEXT,
            chunk_index INTEGER,
            source TEXT
        )""",
        f"CREATE INDEX IF NOT EXISTS chunks_source_type_idx ON {CHUNKS_TABLE} (source_type)",
        f"CREATE INDEX IF NOT EXISTS chunks_fts_idx ON {CHUNKS_TABLE} "
        "USING GIN (to_tsvector('english', text))",
    ]
