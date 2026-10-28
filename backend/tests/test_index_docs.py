from pathlib import Path

import pytest

from app.config import Settings
from retrieval.chunking import chunk_doc
from retrieval.embeddings import get_embedder
from retrieval.index_docs import index_docs, read_docs
from retrieval.vector_store import get_vector_store

FIXTURES = Path(__file__).parent / "fixtures" / "docs"


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


def test_chunk_doc_is_section_aware_bounded_and_deterministic() -> None:
    md = "# T\n\n## A\n\n" + ("word " * 100 + "\n\n") * 3 + "## B\n\nshort"
    chunks = chunk_doc("d", md, max_chars=300)
    assert all(len(c.text) < 400 for c in chunks)
    assert {c.section for c in chunks} == {"A", "B"}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.source_type == "doc" and c.asin is None and c.year is None for c in chunks)
    assert [c.id for c in chunks] == [c.id for c in chunk_doc("d", md, max_chars=300)]


def test_pdf_sections_are_recovered() -> None:
    sections = {c.section for doc_id, md in read_docs(FIXTURES) for c in chunk_doc(doc_id, md)}
    assert {"1. First use", "2. Maintenance", "3. Error codes"} <= sections


def test_index_docs_indexes_md_and_pdf_distinct_from_reviews(store) -> None:
    result = index_docs(FIXTURES)
    assert result["usd"] == 0.0
    with store._connect() as conn:
        count, bad = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE source_type <> 'doc' OR doc_id IS NULL "
            "OR doc_title IS NULL OR section IS NULL OR chunk_index IS NULL) FROM chunks"
        ).fetchone()
    assert count == result["indexed"] > 0 and bad == 0

    query = get_embedder().embed(["How long do I have to return an item?"])[0]
    hit = store.query(query, k=1)[0].chunk
    assert hit.source_type == "doc" and hit.doc_id == "sample-policy"
    assert hit.section == "Return window"
    assert index_docs(FIXTURES)["indexed"] == result["indexed"]
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == count
