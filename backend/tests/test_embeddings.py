import pytest

from app.config import Settings
from retrieval import embeddings
from retrieval.embeddings import (
    AzureEmbedder,
    FreeEmbedder,
    GoAheadRequired,
    get_embedder,
)


def _use(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> None:
    monkeypatch.setattr(embeddings, "get_settings", lambda: Settings(_env_file=None, **kwargs))


def test_factory_returns_free_embedder_in_free_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, provider_mode="free")
    assert isinstance(get_embedder(), FreeEmbedder)


def test_factory_returns_azure_embedder_in_azure_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, provider_mode="azure", azure_embedding_dim=256)
    embedder = get_embedder()
    assert isinstance(embedder, AzureEmbedder)
    assert embedder.dim == 256


def test_azure_embedder_refuses_without_go_ahead() -> None:
    embedder = AzureEmbedder(Settings(_env_file=None))
    with pytest.raises(GoAheadRequired, match="human go-ahead"):
        embedder.embed(["hello"])


def test_azure_embedder_refuses_with_keys_but_no_flag() -> None:
    settings = Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_api_key="k",
        azure_openai_embedding_deployment="d",
    )
    with pytest.raises(GoAheadRequired):
        AzureEmbedder(settings).embed(["hello"])


def test_free_embedder_returns_real_vectors_of_stable_dim() -> None:
    embedder = FreeEmbedder(Settings(_env_file=None, provider_mode="free"))
    try:
        vectors = embedder.embed(["battery lasts long", "screen cracked on arrival"])
    except OSError as exc:
        pytest.skip(f"local embedding model unavailable offline: {exc}")
    assert len(vectors) == 2
    assert all(len(v) == embedder.dim for v in vectors)
    assert vectors[0] != vectors[1]
    assert embedder.embed(["battery lasts long"])[0] == pytest.approx(vectors[0], abs=1e-5)
