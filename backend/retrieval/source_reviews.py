"""Bounded read-only access to existing enriched Silver reviews; no ETL or embeddings."""

import math
from collections import defaultdict
from pathlib import Path

import pyarrow.dataset as ds
from deltalake import DeltaTable
from deltalake.exceptions import DeltaError

from app.config import Settings
from retrieval.chunking import chunk_review, source_parent
from retrieval.index_reviews import REPO_ROOT
from retrieval.schema import Chunk, SearchHit
from retrieval.sufficiency import EvidenceHits

COLUMNS = (
    "asin",
    "category",
    "rating",
    "timestamp",
    "year",
    "title",
    "text",
    "user_id_hash",
    "review_id",
    "parent_id",
    "identity_kind",
    "product_title",
    "price",
    "product_avg_rating",
)


def _read_rows(asins: list[str], scope: dict, settings: Settings) -> tuple[list[dict], str]:
    if not asins or "category" in scope and not scope["category"]:
        return [], "empty_scope"
    if "asin" in scope:
        allowed_asins = scope["asin"]
        allowed_asins = {allowed_asins} if isinstance(allowed_asins, str) else set(allowed_asins)
        asins = [a for a in asins if a in allowed_asins]
        if not asins:
            return [], "empty_scope"
    root = Path(settings.data_lake_path)
    path = (root if root.is_absolute() else REPO_ROOT / root) / "silver"
    table = DeltaTable(str(path))
    version = table.version()
    dataset = DeltaTable(str(path), version=version).to_pyarrow_dataset()
    where = ds.field("asin").isin(asins)
    if "category" in scope:
        categories = scope["category"]
        categories = [categories] if isinstance(categories, str) else categories
        where = where & ds.field("category").isin(categories)
    columns = [c for c in COLUMNS if c in dataset.schema.names]
    rows = []
    for batch in dataset.to_batches(columns=columns, filter=where, batch_size=256):
        rows.extend(batch.to_pylist())
        if len(rows) > settings.source_review_max_rows:
            raise ValueError("Source review read limit exceeded")
    return rows, f"silver:{version}"


def selected_source_reviews(selection: dict, scope: dict, settings: Settings) -> EvidenceHits:
    """Verify supported selection against all source ratings before choosing review examples."""
    columns = selection.get("columns", [])
    required = {"asin", "category", "avg_rating", "review_count"}
    if not required <= set(columns) or not selection.get("minimum_review_count"):
        return EvidenceHits([], {"status": "none", "reason": "unsupported_selection"})
    targets = [dict(zip(columns, row, strict=True)) for row in selection["rows"]]
    allowed = scope.get("category")
    allowed = (
        {allowed} if isinstance(allowed, str) else set(allowed) if allowed is not None else None
    )
    targets = [
        row
        for row in targets
        if row.get("asin") and (allowed is None or row["category"] in allowed)
    ]
    if not targets or len(targets) > 25 or "asin" in scope and not scope["asin"]:
        return EvidenceHits([], {"status": "none", "reason": "empty_scope"})
    requested = scope.get("asin")
    if requested is not None:
        requested = {requested} if isinstance(requested, str) else set(requested)
        targets = [t for t in targets if t["asin"] in requested]
    if not targets:
        return EvidenceHits([], {"status": "none", "reason": "empty_scope"})
    try:
        rows, snapshot = _read_rows(sorted({r["asin"] for r in targets}), scope, settings)
    except (OSError, ValueError, RuntimeError, DeltaError):
        return EvidenceHits([], {"status": "none", "reason": "source_unavailable_or_read_limit"})
    by_product = defaultdict(list)
    for row in rows:
        by_product[(row.get("category"), row.get("asin"))].append(row)
    hits, missing = [], []
    for target in targets:
        key = target["category"], target["asin"]
        reviews = by_product[key]
        ratings = [float(r["rating"]) for r in reviews if r.get("rating") is not None]
        if (
            not ratings
            or len(ratings) != target["review_count"]
            or not math.isclose(
                sum(ratings) / len(ratings), float(target["avg_rating"]), abs_tol=1e-6
            )
        ):
            missing.append(target["asin"])
            continue
        usable = []
        for row in reviews:
            # Negative examples explain a low rating; all ratings above defined the ranking.
            if row.get("rating") is None or float(row["rating"]) > 2:
                continue
            try:
                parent = source_parent(row, snapshot)
            except ValueError:
                continue
            if len(parent.text) > settings.source_review_max_chars:
                continue  # no chopped correction/update presented as a complete review
            usable.append(parent)
        usable.sort(key=lambda p: (p.rating, str(p.timestamp), p.parent_id))
        if not usable:
            missing.append(target["asin"])
        for parent in usable[: settings.source_reviews_per_product]:
            hits.append(
                SearchHit(
                    chunk=Chunk(
                        id=f"source-review:{parent.parent_id}:{parent.content_hash[:12]}",
                        parent_id=parent.parent_id,
                        parent_text=parent.text,
                        text=parent.text,
                        source_type="review",
                        asin=parent.asin,
                        category=parent.category,
                        rating=parent.rating,
                        timestamp=parent.timestamp,
                        year=parent.year,
                        product_title=parent.product_title,
                        price=parent.price,
                        product_avg_rating=parent.product_avg_rating,
                        source_snapshot=snapshot,
                        content_hash=parent.content_hash,
                        normalization_version=parent.normalization_version,
                    ),
                    score=1.0,
                )
            )
    # Round-robin product examples under the query evidence budget.
    groups = defaultdict(list)
    for hit in hits:
        groups[hit.chunk.asin].append(hit)
    hits = [
        group[i]
        for i in range(settings.source_reviews_per_product)
        for group in groups.values()
        if len(group) > i
    ][: settings.retrieval_top_k]
    missing = sorted({t["asin"] for t in targets} - {h.chunk.asin for h in hits})
    return EvidenceHits(
        hits,
        {
            "status": "none" if not hits else ("partial" if missing else "available"),
            "source": "silver_read_only",
            "source_snapshot": snapshot,
            "selection_aggregates_checked": True,
            "missing_product_ids": sorted(set(missing)),
            "unique_review_parents": len({h.chunk.parent_id for h in hits}),
            "interpretation": "Selected negative review examples, not theme prevalence.",
        },
    )


def enrich_indexed_reviews(
    hits: list[SearchHit], scope: dict, settings: Settings
) -> list[SearchHit]:
    """Attach metadata only when original ASIN+raw title/text hash matches legacy chunk ID."""
    legacy = [
        h
        for h in hits
        if h.chunk.source_type == "review" and h.chunk.asin and h.chunk.parent_id is None
    ]
    if not legacy:
        return hits
    try:
        rows, snapshot = _read_rows(sorted({h.chunk.asin for h in legacy}), scope, settings)
    except (OSError, ValueError, RuntimeError, DeltaError):
        return hits
    matches = defaultdict(list)
    for row in rows:
        matches[chunk_review(row).id].append(row)
    enriched = []
    for hit in hits:
        rows = matches.get(hit.chunk.id, [])
        if len(rows) != 1 or rows[0].get("category") != hit.chunk.category:
            enriched.append(hit)  # ambiguity is not resolved with an ASIN-only guess
            continue
        try:
            parent = source_parent(rows[0], snapshot)
        except ValueError:
            enriched.append(hit)
            continue
        enriched.append(
            SearchHit(
                chunk=hit.chunk.model_copy(
                    update={
                        "parent_id": parent.parent_id,
                        "parent_text": parent.text,
                        "text": parent.text,
                        "rating": parent.rating,
                        "timestamp": parent.timestamp,
                        "product_title": parent.product_title,
                        "price": parent.price,
                        "product_avg_rating": parent.product_avg_rating,
                        "source_snapshot": snapshot,
                        "content_hash": parent.content_hash,
                        "normalization_version": parent.normalization_version,
                    }
                ),
                score=hit.score,
            )
        )
    return enriched
