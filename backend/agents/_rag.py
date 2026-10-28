from typing import Literal

from retrieval.embeddings import Embedder
from retrieval.hybrid import hybrid_search
from retrieval.schema import SearchHit
from retrieval.vector_store import Filters, VectorStore


def rag(
    source_type: Literal["review", "doc"],
    query: str,
    scope: Filters | None,
    k: int | None,
    *,
    store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> list[SearchHit]:
    """Scope is merged first so the agent's own source_type always wins over a scope key."""
    filters: Filters = {**(scope or {}), "source_type": source_type}
    if source_type == "doc":
        # Docs are not product-scoped, so a role's product-category filter doesn't apply.
        filters.pop("category", None)
    return hybrid_search(query, k, filters=filters, store=store, embedder=embedder)
