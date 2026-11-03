"""Real tiny Delta source retrieval; no serving DB, embeddings, models or network."""

from pathlib import Path

import pyarrow as pa
import pytest
from deltalake import write_deltalake

from app.config import Settings
from retrieval.chunking import chunk_review
from retrieval.schema import SearchHit
from retrieval.source_reviews import enrich_indexed_reviews, selected_source_reviews


def rows():
    return [
        dict(
            asin="missing",
            category="Electronics",
            rating=float(rating),
            timestamp="2023-01-01T00:00:00Z",
            year=2023,
            title="Battery",
            text=text,
            product_title="Named device",
            user_id_hash=f"private{i}",
        )
        for i, (rating, text) in enumerate(
            [
                (1, "Battery fails<br />quickly."),
                (2, "Poor charging. Update: replacement fixed the problem."),
            ]
        )
    ] + [
        dict(
            asin="other",
            category="Books",
            rating=1.0,
            timestamp="2023-01-01T00:00:00Z",
            year=2023,
            title="Book",
            text="UNAUTHORIZED TEXT",
            product_title="Book",
            user_id_hash="private-book",
        )
    ]


@pytest.fixture
def source(tmp_path):
    write_deltalake(str(tmp_path / "silver"), pa.Table.from_pylist(rows()))
    return Settings(_env_file=None, data_lake_path=str(tmp_path))


def selection(**kwargs):
    return {
        "columns": ["asin", "category", "avg_rating", "review_count"],
        "rows": [["missing", "Electronics", 1.5, 2]],
        "minimum_review_count": 2,
        **kwargs,
    }


def test_missing_index_product_uses_only_verified_selected_source_reviews(source):
    hits = selected_source_reviews(
        selection(), {"category": ["Electronics"], "asin": ["missing"]}, source
    )
    assert len(hits) == 2 and hits.assessment["status"] == "available"
    assert hits.assessment["selection_aggregates_checked"]
    assert {h.chunk.asin for h in hits} == {"missing"}
    assert {h.chunk.product_title for h in hits} == {"Named device"}
    assert {h.chunk.rating for h in hits} == {1.0, 2.0}
    assert all(h.chunk.timestamp.year == 2023 for h in hits)
    assert all(h.chunk.source_snapshot == "silver:0" and h.chunk.parent_id for h in hits)
    assert all(
        "<br" not in h.chunk.text and "private" not in h.chunk.model_dump_json() for h in hits
    )
    assert any("fixed the problem" in h.chunk.parent_text for h in hits)


@pytest.mark.parametrize(
    "scope", [{"category": []}, {"category": ["Books"]}, {"asin": []}, {"asin": ["other"]}]
)
def test_denied_or_empty_scope_never_broadens(source, scope):
    assert not selected_source_reviews(selection(), scope, source)


def test_snapshot_metrics_must_match_before_source_explanations(source):
    wrong = selection(rows=[["missing", "Electronics", 1.0, 2]])
    hits = selected_source_reviews(wrong, {"category": ["Electronics"]}, source)
    assert not hits and hits.assessment["missing_product_ids"] == ["missing"]
    wrong = selection(rows=[["missing", "Electronics", 1.5, 3]])
    assert not selected_source_reviews(wrong, {}, source)


def test_missing_source_and_bounded_read_fail_honestly(source, tmp_path):
    assert not selected_source_reviews(
        selection(), {}, source.model_copy(update={"source_review_max_rows": 1})
    )
    missing = Settings(_env_file=None, data_lake_path=str(tmp_path / "absent"))
    assert not selected_source_reviews(selection(), {}, missing)
    assert not selected_source_reviews({"columns": ["asin"], "rows": [["missing"]]}, {}, source)


def test_metadata_enrichment_requires_unique_exact_chunk_identity(source):
    hit = SearchHit(chunk=chunk_review(rows()[0]), score=0.5)
    out = enrich_indexed_reviews([hit], {"category": ["Electronics"]}, source)
    assert out[0].chunk.rating == 1.0 and out[0].chunk.product_title == "Named device"
    unknown = SearchHit(chunk=hit.chunk.model_copy(update={"id": "different-text"}), score=0.5)
    assert enrich_indexed_reviews([unknown], {}, source)[0].chunk.rating is None
    # Equal text from a different reviewer cannot identify which review was indexed.
    duplicated = rows() + [{**rows()[0], "user_id_hash": "another-private-reviewer"}]
    write_deltalake(
        str(Path(source.data_lake_path) / "silver"),
        pa.Table.from_pylist(duplicated),
        mode="overwrite",
    )
    assert enrich_indexed_reviews([hit], {}, source)[0].chunk.rating is None
