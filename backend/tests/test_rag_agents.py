from agents.docs_rag import docs_rag
from agents.review_rag import review_rag
from retrieval.schema import Chunk, SearchHit
from retrieval.vector_store import Filters

CHUNKS = [
    Chunk(id="r1", source_type="review", text="battery lasts", asin="B01", category="Electronics"),
    Chunk(id="r2", source_type="review", text="blender loud", asin="B02", category="Home"),
    Chunk(id="d1", source_type="doc", text="battery warranty", doc_title="Warranty", section="2"),
    Chunk(id="d2", source_type="doc", text="return policy", doc_title="Returns", section="1"),
]


class FakeEmbedder:
    dim = 3

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class FakeStore:
    """In-memory store honouring filters like build_where (equality or list membership)."""

    def __init__(self) -> None:
        self.seen: list[Filters | None] = []

    def _select(self, filters: Filters | None) -> list[SearchHit]:
        self.seen.append(filters)
        hits = []
        for c in CHUNKS:
            ok = all(
                getattr(c, col) in ([v] if isinstance(v, str) else v)
                for col, v in (filters or {}).items()
            )
            if ok:
                hits.append(SearchHit(chunk=c, score=1.0))
        return hits

    def query(self, vector, k, *, filters=None):
        return self._select(filters)[:k]

    def keyword_query(self, query, k, *, filters=None):
        return self._select(filters)[:k]


def test_review_rag_returns_only_review_hits_with_citation_metadata() -> None:
    hits = review_rag("battery", {}, store=FakeStore(), embedder=FakeEmbedder())
    assert {h.chunk.id for h in hits} == {"r1", "r2"}
    assert all(h.chunk.source_type == "review" and h.chunk.asin and h.chunk.category for h in hits)


def test_docs_rag_returns_only_doc_hits_with_citation_metadata() -> None:
    hits = docs_rag("battery", {}, store=FakeStore(), embedder=FakeEmbedder())
    assert {h.chunk.id for h in hits} == {"d1", "d2"}
    assert all(h.chunk.source_type == "doc" and h.chunk.doc_title and h.chunk.section for h in hits)


def test_scope_is_merged_into_filters_and_source_type_wins() -> None:
    store = FakeStore()
    hits = review_rag(
        "x", {"category": "Home", "source_type": "doc"}, 5, store=store, embedder=FakeEmbedder()
    )
    assert [h.chunk.id for h in hits] == ["r2"]
    assert store.seen[0] == {"category": "Home", "source_type": "review"}


def test_docs_rag_drops_category_scope_so_scoped_roles_still_get_docs() -> None:
    store = FakeStore()
    hits = docs_rag("x", {"category": ["Home"]}, 5, store=store, embedder=FakeEmbedder())
    assert {h.chunk.id for h in hits} == {"d1", "d2"}
    assert store.seen[0] == {"source_type": "doc"}


def test_review_rag_still_applies_category_scope() -> None:
    store = FakeStore()
    hits = review_rag("x", {"category": ["Home"]}, 5, store=store, embedder=FakeEmbedder())
    assert [h.chunk.id for h in hits] == ["r2"]
    assert store.seen[0] == {"category": ["Home"], "source_type": "review"}


def test_docs_rag_keeps_non_category_scope_keys() -> None:
    store = FakeStore()
    hits = docs_rag(
        "x",
        {"category": ["Home"], "doc_title": "Returns"},
        5,
        store=store,
        embedder=FakeEmbedder(),
    )
    assert [h.chunk.id for h in hits] == ["d2"]
    assert store.seen[0] == {"doc_title": "Returns", "source_type": "doc"}
