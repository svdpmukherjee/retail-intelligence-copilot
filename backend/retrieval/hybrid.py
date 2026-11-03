from app.config import get_settings
from retrieval.embeddings import Embedder, get_embedder
from retrieval.rerank import get_reranker
from retrieval.schema import SearchHit
from retrieval.vector_store import Filters, VectorStore, get_vector_store


def rrf_fuse(rankings: list[list[SearchHit]], rrf_k: int) -> list[SearchHit]:
    """Reciprocal-rank fusion: score = sum 1/(rrf_k + rank). Ties break by chunk id."""
    scores: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.chunk.id] = scores.get(hit.chunk.id, 0.0) + 1.0 / (rrf_k + rank)
            by_id.setdefault(hit.chunk.id, hit)
    order = sorted(scores, key=lambda cid: (-scores[cid], cid))
    return [SearchHit(chunk=by_id[cid].chunk, score=scores[cid]) for cid in order]


def hybrid_search(
    query: str,
    k: int | None = None,
    *,
    filters: Filters | None = None,
    store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> list[SearchHit]:
    """Vector + keyword retrieval -> RRF -> rerank -> top-k. `filters` is the access choke point."""
    settings = get_settings()
    k = settings.retrieval_top_k if k is None else k
    store = store or get_vector_store()
    embedder = embedder or get_embedder()
    compatible = getattr(store, "require_compatible", None)
    if compatible:
        compatible(embedder)  # reject before embedding/query, including same-dimension mismatches
    vector = embedder.embed([query])[0]
    n = settings.hybrid_candidates
    from retrieval.sufficiency import lexical_query, select_evidence

    vectors = store.query(vector, n, filters=filters)
    keywords = store.keyword_query(
        lexical_query(query) if compatible else query, n, filters=filters
    )
    fused = rrf_fuse([vectors, keywords], settings.rrf_k)
    reranked = get_reranker(settings).rerank(query, fused[: settings.rerank_candidates])
    if compatible:
        selected = select_evidence(
            query,
            reranked,
            vectors,
            filters=filters,
            minimum_similarity=settings.evidence_min_similarity,
            k=k,
        )
        selected.assessment["lexical_candidates"] = len(keywords)
        return selected
    return reranked[:k]
