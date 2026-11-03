"""Immutable bounded evidence bundles for isolated Stage 3 verification.

SQLite holds real vectors and FTS5; this fixture adapter never migrates Postgres.
A bundle binds SQL Gold, parents, index and embedding identity as one version.
"""

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from deltalake import DeltaTable, write_deltalake

from retrieval.chunking import CHUNKER_VERSION, chunk_parent
from retrieval.normalization import NORMALIZATION_VERSION
from retrieval.provenance import (
    CorpusManifest,
    EvidenceCompatibilityError,
    ParentSource,
    content_hash,
)
from retrieval.schema import Chunk, SearchHit


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for entry in sorted(path.rglob("*")):
        if entry.is_file():
            digest.update(entry.relative_to(path).as_posix().encode())
            digest.update(file_hash(entry).encode())
    return digest.hexdigest()


def member(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Bundle member escapes its version directory")
    return path


class EvidenceBundleStore:
    """Read-only version; compatibility checked before query embedding in hybrid_search."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.manifest = CorpusManifest.model_validate_json(
            (self.root / "manifest.json").read_text()
        )
        self.index_path = member(self.root, self.manifest.index_file)
        parents_path = member(self.root, self.manifest.parents_file)
        if file_hash(self.index_path) != self.manifest.index_sha256:
            raise EvidenceCompatibilityError("Index checksum differs from manifest")
        if file_hash(parents_path) != self.manifest.parents_sha256:
            raise EvidenceCompatibilityError("Parent checksum differs from manifest")
        self.parents = {
            p.parent_id: p
            for p in (ParentSource.model_validate(x) for x in json.loads(parents_path.read_text()))
        }
        if len(self.parents) != self.manifest.parent_count:
            raise EvidenceCompatibilityError("Parent count differs from manifest")
        chunks = self._chunks(None)
        if len(chunks) != self.manifest.chunk_count:
            raise EvidenceCompatibilityError("Chunk count differs from manifest")
        for chunk in chunks:
            parent = self.parents.get(chunk.parent_id)
            if (
                parent is None
                or parent.content_hash != content_hash(parent.text)
                or chunk.start_char is None
                or chunk.end_char is None
                or not 0 <= chunk.start_char < chunk.end_char <= len(parent.text)
                or chunk.content_hash != parent.content_hash
                or chunk.text != parent.text[chunk.start_char : chunk.end_char]
                or any(
                    getattr(chunk, key) != getattr(parent, key)
                    for key in (
                        "category",
                        "asin",
                        "source_type",
                        "source",
                        "rating",
                        "timestamp",
                        "product_title",
                        "source_snapshot",
                        "normalization_version",
                    )
                )
            ):
                raise EvidenceCompatibilityError("Chunk provenance differs from parent")
            vector = chunk.embedding
            if (
                not vector
                or len(vector) != self.manifest.embedding.dimensions
                or not all(math.isfinite(x) for x in vector)
                or not any(vector)
            ):
                raise EvidenceCompatibilityError("Invalid indexed embedding")
        self.structured_path = member(self.root, self.manifest.structured_gold)
        binding = self.manifest.source_versions.get("structured_gold_sha256")
        if not binding or tree_hash(self.structured_path) != binding:
            raise EvidenceCompatibilityError("SQL Gold differs from the bound snapshot")

    def require_compatible(self, embedder) -> None:
        identity = getattr(embedder, "identity", None)
        if identity is None:
            raise EvidenceCompatibilityError("Query embedder has no verified identity")
        self.manifest.embedding.require_match(identity)

    def ensure_schema(self) -> None:
        raise ValueError("Immutable bundle; build a new isolated version")

    def upsert(self, chunks: list[Chunk]) -> int:
        raise ValueError("Immutable bundle; build a new isolated version")

    def _connect(self):
        return sqlite3.connect(self.index_path.as_uri() + "?mode=ro", uri=True)

    def _chunks(self, filters: dict | None) -> list[Chunk]:
        from retrieval.vector_store import build_where

        build_where(filters)  # identical allowlist; empty intersections remain empty
        with self._connect() as conn:
            chunks = [
                Chunk.model_validate_json(row[0])
                for row in conn.execute("SELECT payload FROM chunks")
            ]
        return [
            c
            for c in chunks
            if all(
                (getattr(c, key) == value if isinstance(value, str) else getattr(c, key) in value)
                for key, value in (filters or {}).items()
            )
        ]

    def parent(self, parent_id: str, *, filters: dict) -> ParentSource | None:
        # Parent context must never bypass retrieval scope.
        allowed = {c.parent_id for c in self._chunks(filters)}
        return self.parents.get(parent_id) if parent_id in allowed else None

    def _hit(self, chunk: Chunk, score: float) -> SearchHit:
        parent = self.parents[chunk.parent_id]
        chunk = chunk.model_copy(update={"parent_text": parent.text})
        return SearchHit(chunk=chunk, score=score)

    def query(self, vector: list[float], k: int, *, filters: dict | None = None) -> list[SearchHit]:
        if len(vector) != self.manifest.embedding.dimensions:
            raise EvidenceCompatibilityError("Query vector dimensions differ")
        norm = math.sqrt(sum(x * x for x in vector))
        if not norm or not all(math.isfinite(x) for x in vector):
            raise ValueError("Query vector must be finite and nonzero")
        hits = []
        for chunk in self._chunks(filters):
            other = chunk.embedding
            denom = norm * math.sqrt(sum(x * x for x in other))
            score = sum(a * b for a, b in zip(vector, other, strict=True)) / denom
            hits.append(self._hit(chunk, score))
        return sorted(hits, key=lambda h: (-h.score, h.chunk.id))[:k]

    def keyword_query(self, query: str, k: int, *, filters: dict | None = None) -> list[SearchHit]:
        terms = re.findall(r"\w+", query)
        if not terms:
            return []
        # Safe FTS grammar; OR measures focused lexical contribution independently.
        expression = " OR ".join('"' + t + '"' for t in terms)
        allowed = {c.id: c for c in self._chunks(filters)}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, bm25(lexical) FROM lexical WHERE lexical MATCH ? "
                "ORDER BY bm25(lexical), id",
                (expression,),
            ).fetchall()
        return [self._hit(allowed[key], -score) for key, score in rows if key in allowed][:k]


def build_fixture_bundle(
    root: Path,
    *,
    version: str,
    parents: list[ParentSource],
    structured_rows: list[dict],
    embedder,
    seed: str,
    previous: EvidenceBundleStore | None = None,
) -> dict:
    """Build an exclusive new fixture version (<=100 reviews/3 docs/500 chunks).

    No serving path is accepted, no remote embedder is accepted, and no prior
    version is changed. A failed build leaves no published bundle.
    """
    import pyarrow as pa

    from retrieval.embeddings import FreeEmbedder

    if not isinstance(embedder, FreeEmbedder) or not embedder._offline:
        raise ValueError("Fixture bundles require the cached local embedder in offline mode")
    if root.exists():
        raise ValueError("Version directory already exists; refusing overwrite")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", version):
        raise ValueError("Invalid corpus version")
    if (
        sum(p.source_type == "review" for p in parents) > 100
        or sum(p.source_type == "doc" for p in parents) > 3
    ):
        raise ValueError("Fixture source limit exceeded")
    if len(structured_rows) > 100 or not structured_rows or not parents:
        raise ValueError("Fixture structured SQL rows must be bounded and nonempty")
    if len({p.parent_id for p in parents}) != len(parents):
        raise ValueError("Duplicate/ambiguous parent identity")
    if any(not p.source_snapshot.startswith("fixture:") for p in parents):
        raise ValueError(
            "This builder accepts synthetic fixture snapshots only; real backfill is gated"
        )
    if any(
        p.content_hash != content_hash(p.text) or p.normalization_version != NORMALIZATION_VERSION
        for p in parents
    ):
        raise ValueError("Parent content/version differs from normalized source")
    sql_products = {(r.get("category"), r.get("asin")) for r in structured_rows}
    if any(p.source_type == "review" and (p.category, p.asin) not in sql_products for p in parents):
        raise ValueError("Candidate reviews must belong to the SQL snapshot")
    identity = embedder.identity
    identity.require_match(identity)
    if previous:
        previous.manifest.embedding.require_match(identity)
    chunks = [
        c
        for p in parents
        for c in chunk_parent(p, embedder.tokenizer, max_tokens=embedder.max_tokens, overlap=24)
    ]
    if len(chunks) > 500:
        raise ValueError("Fixture chunk limit exceeded")
    old_chunks = {c.id: c for c in previous._chunks(None)} if previous else {}
    # Reuse vectors only with matching identity AND byte-identical text/metadata lineage.
    new = [c for c in chunks if c.id not in old_chunks or c.text != old_chunks[c.id].text]
    vectors = embedder.embed([c.text for c in new])
    fresh = dict(zip((c.id for c in new), vectors, strict=True))
    for chunk in chunks:
        chunk.embedding = fresh[chunk.id] if chunk.id in fresh else old_chunks[chunk.id].embedding
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".evidence-", dir=root.parent))
    try:
        parent_file = staging / "parents.json"
        parent_file.write_text(
            json.dumps([p.model_dump(mode="json") for p in parents], sort_keys=True)
        )
        index = staging / "index.sqlite"
        with sqlite3.connect(index) as conn:
            conn.execute("CREATE TABLE chunks (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            conn.execute(
                "CREATE VIRTUAL TABLE lexical USING fts5("
                "id UNINDEXED, text, tokenize='porter unicode61')"
            )
            conn.executemany(
                "INSERT INTO chunks VALUES (?, ?)",
                [(c.id, c.model_dump_json()) for c in chunks],
            )
            conn.executemany("INSERT INTO lexical VALUES (?, ?)", [(c.id, c.text) for c in chunks])
        gold = staging / "gold" / "structured"
        write_deltalake(str(gold), pa.Table.from_pylist(structured_rows))
        manifest = CorpusManifest(
            corpus_version=version,
            embedding=identity,
            source_versions={
                **{p.parent_id: p.source_snapshot for p in parents},
                "structured_gold_sha256": tree_hash(gold),
                "structured_delta_version": str(DeltaTable(str(gold)).version()),
            },
            selection_seed=seed,
            normalization_version=NORMALIZATION_VERSION,
            chunker_version=CHUNKER_VERSION,
            chunk_tokens=embedder.max_tokens,
            chunk_overlap=24,
            parent_count=len(parents),
            chunk_count=len(chunks),
            parents_sha256=file_hash(parent_file),
            index_sha256=file_hash(index),
        )
        (staging / "manifest.json").write_text(manifest.model_dump_json(indent=2))
        # Exclusive publication; root never points at a half-built index.
        if root.exists():
            raise ValueError("Version directory appeared during build")
        staging.rename(root)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    new_parents = {p.parent_id: p.content_hash for p in parents}
    old_parents = (
        {p.parent_id: p.content_hash for p in previous.parents.values()} if previous else {}
    )
    return {
        "corpus_version": version,
        "parents": len(parents),
        "chunks": len(chunks),
        "embedded_chunks": len(new),
        "reused_chunks": len(chunks) - len(new),
        "deleted_parents": sorted(old_parents.keys() - new_parents.keys()),
        "edited_parents": sorted(
            k for k in old_parents.keys() & new_parents.keys() if old_parents[k] != new_parents[k]
        ),
        "hosted_usd": 0,
    }


def write_fixture_pointer(pointer: Path, bundle: Path) -> None:
    """Atomic pointer helper confined to one isolated fixture workspace; rollback is the same op."""
    bundle = bundle.resolve()
    if pointer.parent.resolve() != bundle.parent:
        raise ValueError("Fixture pointer and versions must share a workspace")
    EvidenceBundleStore(bundle)  # validate all bound members before changing pointer
    temp = pointer.with_suffix(".new")
    with temp.open("x") as stream:
        json.dump({"bundle": bundle.name}, stream)
    os.replace(temp, pointer)


def open_bundle(path: str | Path) -> EvidenceBundleStore:
    path = Path(path).resolve()
    if path.is_file():
        value = json.loads(path.read_text())
        return EvidenceBundleStore(member(path.parent, value["bundle"]))
    return EvidenceBundleStore(path)


_pinned_bundle: ContextVar[EvidenceBundleStore | None] = ContextVar("evidence_bundle", default=None)


def configured_bundle(path: str) -> EvidenceBundleStore:
    """A pipeline turn uses the same immutable SQL/index version across pointer switches."""
    return _pinned_bundle.get() or open_bundle(path)


@contextmanager
def pin_bundle(path: str) -> Iterator[EvidenceBundleStore]:
    bundle = open_bundle(path)
    token = _pinned_bundle.set(bundle)
    try:
        yield bundle
    finally:
        _pinned_bundle.reset(token)
