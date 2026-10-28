from collections.abc import Iterator

import pytest

from app.config import Settings
from retrieval import hybrid
from retrieval.embeddings import GoAheadRequired
from retrieval.hybrid import hybrid_search, rrf_fuse
from retrieval.rerank import AzureReranker, NoReranker, get_reranker
from retrieval.schema import Chunk, SearchHit, make_chunk_id
from retrieval.vector_store import PgVectorStore, build_where

DIM = 3


def _chunk(key: str, text: str, vec: list[float], source_type: str = "review", **kw: object):
    return Chunk(id=make_chunk_id(key), source_type=source_type, text=text, embedding=vec, **kw)


def _hit(key: str) -> SearchHit:
    return SearchHit(chunk=Chunk(id=key, source_type="review", text=key), score=0.0)


class FakeEmbedder:
    dim = DIM

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_rrf_fuse_scores_and_tie_breaks_by_id() -> None:
    fused = rrf_fuse([[_hit("a"), _hit("b")], [_hit("b"), _hit("c")]], rrf_k=60)
    assert [h.chunk.id for h in fused] == ["b", "a", "c"]
    assert fused[0].score == pytest.approx(1 / 62 + 1 / 61)
    tie = rrf_fuse([[_hit("z")], [_hit("y")]], rrf_k=60)
    assert [h.chunk.id for h in tie] == ["y", "z"]


def test_build_where_is_parameterised_and_allowlisted() -> None:
    where, params = build_where({"source_type": "doc", "category": ["A", "B"]})
    assert where == "WHERE source_type = %s AND category = ANY(%s) "
    assert params == ["doc", ["A", "B"]]
    assert build_where(None) == ("", [])
    with pytest.raises(ValueError, match="unsupported filter"):
        build_where({"text; DROP TABLE chunks": "x"})


def test_azure_reranker_raises_gated() -> None:
    with pytest.raises(GoAheadRequired, match="go-ahead"):
        AzureReranker(Settings(_env_file=None, reranker="azure")).rerank("q", [_hit("a")])
    assert isinstance(get_reranker(Settings(_env_file=None, reranker="azure")), AzureReranker)


def test_reranker_none_preserves_order() -> None:
    hits = [_hit("b"), _hit("a")]
    assert get_reranker(Settings(_env_file=None)).rerank("q", hits) == hits
    assert isinstance(get_reranker(Settings(_env_file=None)), NoReranker)


@pytest.fixture
def store() -> Iterator[PgVectorStore]:
    url = Settings().database_url
    if url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    s = PgVectorStore(url.get_secret_value(), DIM)
    try:
        with s._connect(vectors=False) as conn:
            conn.execute("DROP TABLE IF EXISTS chunks")
        s.ensure_schema()
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    s.upsert(
        [
            _chunk("r1", "battery life is excellent", [0.0, 1.0, 0.0], category="Electronics"),
            _chunk("r2", "screen cracked quickly", [0.9, 0.1, 0.0], category="Electronics"),
            _chunk("r3", "great blender for smoothies", [0.0, 0.0, 1.0], category="Home"),
            _chunk(
                "d1", "warranty covers battery defects", [0.8, 0.2, 0.0], "doc", source="policy"
            ),
        ]
    )
    yield s
    with s._connect(vectors=False) as conn:
        conn.execute("DROP TABLE chunks")


def test_keyword_query_returns_keyword_match_and_respects_filters(store: PgVectorStore) -> None:
    texts = {h.chunk.text for h in store.keyword_query("battery", 5)}
    assert texts == {"battery life is excellent", "warranty covers battery defects"}
    docs = store.keyword_query("battery", 5, filters={"source_type": "doc"})
    assert [h.chunk.text for h in docs] == ["warranty covers battery defects"]
    assert store.keyword_query("battery", 5, filters={"category": "Home"}) == []


def test_hybrid_search_fuses_vector_and_keyword(
    store: PgVectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # r2 is nearest by vector, r1 is the only review keyword match; both must surface.
    out = hybrid_search(
        "battery", 3, filters={"source_type": "review"}, store=store, embedder=FakeEmbedder()
    )
    texts = [h.chunk.text for h in out]
    assert "screen cracked quickly" in texts and "battery life is excellent" in texts
    assert all(h.chunk.source_type == "review" for h in out)
    docs = hybrid_search(
        "battery", 5, filters={"source_type": "doc"}, store=store, embedder=FakeEmbedder()
    )
    assert [h.chunk.id for h in docs] == [make_chunk_id("d1")]
    scoped = hybrid_search(
        "battery", 5, filters={"category": "Home"}, store=store, embedder=FakeEmbedder()
    )
    assert {h.chunk.category for h in scoped} == {"Home"}


def test_reranker_none_keeps_fused_order_in_hybrid(
    store: PgVectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hybrid, "get_settings", lambda: Settings(_env_file=None))
    out = hybrid_search("battery", 4, store=store, embedder=FakeEmbedder())
    scores = [h.score for h in out]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_search_with_azure_reranker_raises_gated(
    store: PgVectorStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hybrid, "get_settings", lambda: Settings(_env_file=None, reranker="azure"))
    with pytest.raises(GoAheadRequired):
        hybrid_search("battery", 2, store=store, embedder=FakeEmbedder())
