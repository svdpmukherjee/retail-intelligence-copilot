import json
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.config import Settings, get_settings
from retrieval.provenance import EmbeddingIdentity

Vector = list[float]

AZURE_EMBEDDING_MODEL = "text-embedding-3-small"
AZURE_API_VERSION = "2024-02-01"


class GoAheadRequired(RuntimeError):
    """Raised when a paid/cloud path is invoked without explicit human go-ahead."""


class Embedder(Protocol):
    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[Vector]: ...


class FreeEmbedder:
    """Local sentence-transformers model; $0. Model loads lazily so import stays cheap."""

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.embedding_model_free
        self._batch_size = settings.embedding_batch_size
        self._revision = settings.embedding_model_revision
        self._offline = settings.embedding_local_files_only
        self._model = None
        self._resolved_revision: str | None = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            model_path = self._model_name
            if self._offline:
                from huggingface_hub import snapshot_download

                snapshot = Path(
                    snapshot_download(
                        self._model_name, revision=self._revision, local_files_only=True
                    )
                )
                model_path = str(snapshot)
                self._resolved_revision = snapshot.name
            self._model = SentenceTransformer(
                model_path,
                revision=self._revision if not self._offline else None,
                local_files_only=self._offline,
            )
        return self._model

    @property
    def identity(self) -> EmbeddingIdentity:
        from retrieval.provenance import EvidenceCompatibilityError, content_hash

        # Load the exact cached path whose revision is recorded, rather than
        # re-resolving a mutable cache ref after a model was loaded.
        if not self._offline:
            raise EvidenceCompatibilityError("Verified local identity requires an offline snapshot")
        model = self._load()
        tokenizer_config = json.loads(model.tokenizer.backend_tokenizer.to_str())
        # encode() changes runtime padding/truncation state, not tokenizer identity.
        tokenizer_config.pop("padding", None)
        tokenizer_config.pop("truncation", None)
        tokenizer_hash = content_hash(json.dumps(tokenizer_config, sort_keys=True))
        return EmbeddingIdentity(
            provider="local",
            model=self._model_name,
            revision=self._resolved_revision,
            dimensions=self.dim,
            tokenizer=tokenizer_hash,
            preprocessing=f"sentence-transformers-normalized-v1:max_tokens={self.max_tokens}",
        )

    @property
    def tokenizer(self) -> Any:
        return self._load().tokenizer

    @property
    def max_tokens(self) -> int:
        return self._load().max_seq_length

    @property
    def dim(self) -> int:
        return int(self._load().get_embedding_dimension())

    def embed(self, texts: list[str]) -> list[Vector]:
        if not texts:
            return []
        vectors = self._load().encode(texts, batch_size=self._batch_size, normalize_embeddings=True)
        return vectors.tolist()


class AzureEmbedder:
    """Azure OpenAI text-embedding-3-small. Gated: refuses without keys + go-ahead flag."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dim = settings.azure_embedding_dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def identity(self) -> EmbeddingIdentity:
        from retrieval.provenance import EvidenceCompatibilityError

        if not self._settings.azure_embedding_revision:
            raise EvidenceCompatibilityError("Azure embedding deployment revision is unverified")
        return EmbeddingIdentity(
            provider="azure",
            model=AZURE_EMBEDDING_MODEL,
            revision=self._settings.azure_embedding_revision,
            dimensions=self.dim,
            tokenizer="azure-managed",
            preprocessing="azure-default-v1",
        )

    def _require_go_ahead(self) -> tuple[str, str, str]:
        s = self._settings
        if not (
            s.azure_embedding_go_ahead
            and s.azure_openai_endpoint
            and s.azure_openai_api_key
            and s.azure_openai_embedding_deployment
        ):
            raise GoAheadRequired(
                "Azure embedding requires human go-ahead: set AZURE_EMBEDDING_GO_AHEAD=true "
                "plus AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and "
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT. Use PROVIDER_MODE=free for $0 runs."
            )
        return (
            s.azure_openai_endpoint.rstrip("/"),
            s.azure_openai_api_key.get_secret_value(),
            s.azure_openai_embedding_deployment,
        )

    def embed(self, texts: list[str]) -> list[Vector]:
        endpoint, key, deployment = self._require_go_ahead()
        if not texts:
            return []
        url = f"{endpoint}/openai/deployments/{deployment}/embeddings"
        vectors: list[Vector] = []
        step = self._settings.embedding_batch_size
        for start in range(0, len(texts), step):
            resp = httpx.post(
                url,
                params={"api-version": AZURE_API_VERSION},
                headers={"api-key": key},
                json={"input": texts[start : start + step], "dimensions": self._dim},
                timeout=60,
            )
            resp.raise_for_status()
            data = sorted(resp.json()["data"], key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)
        return vectors


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.provider_mode == "azure":
        return AzureEmbedder(settings)
    if settings.evidence_bundle_path:
        settings = settings.model_copy(update={"embedding_local_files_only": True})
    return FreeEmbedder(settings)
