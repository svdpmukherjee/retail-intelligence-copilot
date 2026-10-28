from agents._rag import rag
from retrieval.embeddings import Embedder
from retrieval.schema import SearchHit
from retrieval.vector_store import Filters, VectorStore


def review_rag(
    query: str,
    scope: Filters | None = None,
    k: int | None = None,
    *,
    store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> list[SearchHit]:
    """Hybrid retrieval over reviews chunks only; `scope` narrows it further (access hook)."""
    return rag("review", query, scope, k, store=store, embedder=embedder)
