"""Versioned evidence contracts. Unknown embedding lineage is never compatible."""

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCompatibilityError(ValueError):
    pass


class EmbeddingIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: str
    model: str
    revision: str
    dimensions: int = Field(gt=0)
    tokenizer: str
    preprocessing: str

    def require_match(self, other: "EmbeddingIdentity") -> None:
        values = (
            self.provider,
            self.model,
            self.revision,
            self.tokenizer,
            self.preprocessing,
        )
        if any(not x or x.lower() in ("unknown", "unverified") for x in values):
            raise EvidenceCompatibilityError("Embedding provenance is unverified")
        if self != other:
            raise EvidenceCompatibilityError("Query and corpus embedding identities differ")


class ParentSource(BaseModel):
    parent_id: str
    identity_kind: str
    source_type: Literal["review", "doc"]
    text: str  # normalized and PII-redacted, including corrections/updates
    source_snapshot: str
    source_hash: str  # hash only; original unredacted source is not copied
    content_hash: str
    normalization_version: str
    category: str | None = None
    asin: str | None = None
    rating: float | None = Field(default=None, ge=1, le=5)
    timestamp: datetime | None = None
    product_title: str | None = None
    price: float | None = None
    product_avg_rating: float | None = None
    year: int | None = None
    doc_id: str | None = None
    doc_title: str | None = None
    section: str | None = None
    source: str | None = None
    sample_membership: list[str] = Field(default_factory=list)


class CorpusManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: Literal[2] = 2
    corpus_version: str
    embedding: EmbeddingIdentity
    source_versions: dict[str, str]
    selection_seed: str
    normalization_version: str
    chunker_version: str
    chunk_tokens: int
    chunk_overlap: int
    parent_count: int
    chunk_count: int
    parents_sha256: str
    index_sha256: str
    # All components belong to this bundle; no loose SQL/index pointer pairing.
    structured_gold: str = "gold/structured"
    index_file: str = "index.sqlite"
    parents_file: str = "parents.json"


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def review_parent_id(row: dict) -> tuple[str, str]:
    """Accept a projected ID or private pre-projection key, never ASIN/text alone."""
    if row.get("parent_id") and row.get("identity_kind"):
        return row["parent_id"], row["identity_kind"]
    if row.get("review_id"):
        values, kind = [row.get("category"), row["review_id"]], "upstream_review_id_v1"
    elif all(row.get(k) is not None for k in ("category", "asin", "user_id_hash", "timestamp")):
        values = [row[k] for k in ("category", "asin", "user_id_hash", "timestamp")]
        kind = "source_tuple_v1"
    else:
        raise ValueError("Stable private review identity is missing; no ASIN/text fallback")
    return content_hash(json.dumps(values, default=str, ensure_ascii=False)), kind
