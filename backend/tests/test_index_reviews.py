import pytest

from app.config import Settings
from retrieval.index_reviews import (
    index_reviews,
    iter_gold_review_batches,
    read_gold_reviews,
)
from retrieval.vector_store import get_vector_store


@pytest.fixture
def store():
    if Settings().database_url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    s = get_vector_store()
    try:
        # Vector dim is fixed at table creation; start clean so another test's dim can't leak.
        with s._connect(vectors=False) as conn:
            conn.execute("DROP TABLE IF EXISTS chunks")
        s.ensure_schema()
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    yield s
    with s._connect(vectors=False) as conn:
        conn.execute("DROP TABLE chunks")


def test_index_reviews_on_gold_sample_is_populated_and_idempotent(store) -> None:
    expected = len({(r["asin"], r["title"], r["text"]) for r in read_gold_reviews()})

    first = index_reviews()
    second = index_reviews()

    assert first["indexed"] == second["indexed"] == len(read_gold_reviews())
    assert first["usd"] == 0.0
    with store._connect() as conn:
        count, bad = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE source_type <> 'review' OR category IS NULL "
            "OR asin IS NULL OR year IS NULL) FROM chunks"
        ).fetchone()
    assert count == expected
    assert bad == 0


def test_iter_gold_review_batches_covers_every_row_in_bounded_batches() -> None:
    total = len(read_gold_reviews())
    size = max(1, total // 3)

    batches = list(iter_gold_review_batches(size))

    assert len(batches) > 1
    assert all(0 < len(b) <= size for b in batches)
    assert sum(len(b) for b in batches) == total


def test_read_gold_reviews_honours_limit() -> None:
    rows = read_gold_reviews(2)

    assert isinstance(rows, list)
    assert len(rows) <= 2
