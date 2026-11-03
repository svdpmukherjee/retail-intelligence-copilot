"""Deterministic bounded fixture selection; records diagnostic sampling bias."""

from collections import defaultdict

from retrieval.provenance import content_hash, review_parent_id


def select_reviews(
    rows: list[dict],
    *,
    seed: str,
    per_product_stratum: int = 1,
    diagnostic_products: set[tuple[str, str]] | None = None,
) -> list[dict]:
    if len(rows) > 100 or per_product_stratum < 1:
        raise ValueError("Isolated selection is bounded to 100 input fixture reviews")
    groups = defaultdict(list)
    identities = set()
    for row in rows:
        if not row.get("category") or not row.get("asin") or row.get("rating") is None:
            raise ValueError("Selection requires product/category/rating metadata")
        parent_id, kind = review_parent_id(row)
        if parent_id in identities:
            raise ValueError("Duplicate/ambiguous source review identity")
        identities.add(parent_id)
        rating = float(row["rating"])
        if not 1 <= rating <= 5:
            raise ValueError("Review rating must be within 1–5")
        band = "negative" if rating <= 2 else ("neutral" if rating == 3 else "positive")
        groups[(row["category"], row["asin"], row.get("year"), band)].append(
            {**row, "parent_id": parent_id, "identity_kind": kind}
        )
    selected = {}
    for key, group in sorted(groups.items(), key=lambda x: str(x[0])):
        group.sort(key=lambda row: content_hash(seed + row["parent_id"]))
        for rank, row in enumerate(group):
            membership = []
            if rank < per_product_stratum:
                membership.append("product_date_rating_core")
            if key[:2] in (diagnostic_products or set()):
                membership.append("low_rating_diagnostic_nonrepresentative")
            if membership:
                if row["parent_id"] in selected:
                    raise ValueError("Duplicate/ambiguous source review identity")
                selected[row["parent_id"]] = {**row, "sample_membership": membership}
    return [selected[key] for key in sorted(selected)]
