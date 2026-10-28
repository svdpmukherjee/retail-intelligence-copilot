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
    vector = (embedder or get_embedder()).embed([query])[0]
    n = settings.hybrid_candidates
    fused = rrf_fuse(
        [
            store.query(vector, n, filters=filters),
            store.keyword_query(query, n, filters=filters),
        ],
        settings.rrf_k,
    )
    reranked = get_reranker(settings).rerank(query, fused[: settings.rerank_candidates])
    return reranked[:k]
