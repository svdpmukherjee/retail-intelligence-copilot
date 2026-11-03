"""Bounded candidate evidence selection; scores are relevance, never confidence."""

import re

from retrieval.schema import SearchHit

# Query scaffolding is not useful lexical evidence. Product/category/issue words remain.
STOP = set(
    "what whats which why how do does did are is was were our the a an and or "
    "of to for in on with about customers customer reviews review products product "
    "say says most least lowest highest rated rating ratings unhappy disappointing "
    "complain complaints praise explain please tell me us".split()
)


class EvidenceHits(list):
    def __init__(self, hits: list[SearchHit], assessment: dict) -> None:
        super().__init__(hits)
        self.assessment = assessment


def lexical_query(query: str) -> str:
    return " ".join(dict.fromkeys(w for w in re.findall(r"[\w]+", query.lower()) if w not in STOP))


def select_evidence(
    query: str,
    fused: list[SearchHit],
    vectors: list[SearchHit],
    *,
    filters: dict | None,
    minimum_similarity: float,
    k: int,
) -> EvidenceHits:
    """Use raw cosine, metadata and unique parents; never threshold an RRF score."""
    if k < 1:
        raise ValueError("Evidence selection needs a positive result limit")
    scores = {h.chunk.id: h.score for h in vectors}
    negative = bool(
        re.search(r"\b(complain\w*|unhappy|disappoint\w*|problems?|negative)\b", query, re.I)
    )
    positive = bool(re.search(r"\b(prais\w*|positive|like|love)\b", query, re.I)) and not negative
    chosen, parents = [], set()
    for hit in fused:
        c = hit.chunk
        if scores.get(c.id, -1) < minimum_similarity:
            continue
        if c.source_type == "review":
            if negative and (c.rating is None or c.rating > 2):
                continue
            if positive and (c.rating is None or c.rating < 4):
                continue
        key = c.parent_id or c.id
        if key in parents:
            continue
        parents.add(key)
        chosen.append(hit)
        if len(chosen) >= k:
            break
    expected = (filters or {}).get("asin", [])
    expected = {expected} if isinstance(expected, str) else set(expected)
    covered = {h.chunk.asin for h in chosen if h.chunk.asin}
    missing = expected - covered
    return EvidenceHits(
        chosen,
        {
            "status": "none" if not chosen else ("partial" if missing else "available"),
            "unique_review_parents": len(
                {h.chunk.parent_id for h in chosen if h.chunk.source_type == "review"}
            ),
            "missing_product_ids": sorted(missing),
            "minimum_raw_cosine": minimum_similarity,
            "vector_candidates": len(vectors),
            "candidate_scope": "isolated_versioned_bundle",
            "interpretation": (
                "Qualitative examples; no population prevalence " "or factual-support guarantee."
            ),
        },
    )
