from typing import Protocol

from app.config import Settings, get_settings
from retrieval.embeddings import GoAheadRequired
from retrieval.schema import SearchHit


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]: ...


class NoReranker:
    """Identity passthrough: keeps the fused order and score. $0."""

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        return list(hits)


class LocalReranker:
    """Local sentence-transformers cross-encoder; $0. Loads lazily so `none` never imports it."""

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.rerank_model_local
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        if not hits:
            return []
        scores = self._load().predict([(query, h.chunk.text) for h in hits])
        scored = [
            SearchHit(chunk=h.chunk, score=float(s)) for h, s in zip(hits, scores, strict=True)
        ]
        return sorted(scored, key=lambda h: (-h.score, h.chunk.id))


class AzureReranker:
    """Hosted reranker. Inert: refuses unless a human has given the go-ahead."""

    def __init__(self, settings: Settings) -> None:
        self._go_ahead = settings.rerank_go_ahead

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        if not self._go_ahead:
            raise GoAheadRequired(
                "Azure reranker requires human go-ahead (RERANK_GO_AHEAD=true). "
                "Use RERANKER=none or local for $0 runs."
            )
        raise GoAheadRequired("Azure reranker is not implemented in this build.")


def get_reranker(settings: Settings | None = None) -> Reranker:
    settings = settings or get_settings()
    if settings.reranker == "local":
        return LocalReranker(settings)
    if settings.reranker == "azure":
        return AzureReranker(settings)
    return NoReranker()
