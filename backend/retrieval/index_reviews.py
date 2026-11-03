import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from deltalake import DeltaTable

from app.config import get_settings
from app.cost import CostLedger
from retrieval.chunking import chunk_review
from retrieval.embeddings import get_embedder
from retrieval.schema import Chunk
from retrieval.vector_store import get_vector_store

REPO_ROOT = Path(__file__).resolve().parents[2]
# text-embedding-3-small list price; the free/local embedder is $0.
AZURE_USD_PER_1M_TOKENS = 0.02
CHARS_PER_TOKEN = 4  # rough estimate; only used to enforce the spend cap


def gold_reviews_path() -> Path:
    """`gold/reviews` under the M2 data lake root (relative roots resolve from the repo root)."""
    root = Path(get_settings().data_lake_path)
    return (root if root.is_absolute() else REPO_ROOT / root) / "gold" / "reviews"


def _require_gold_reviews() -> Path:
    path = gold_reviews_path()
    if not path.exists():
        raise FileNotFoundError(f"Gold reviews not found at {path}; run the M2 pipeline first.")
    return path


def iter_gold_review_batches(batch_size: int) -> Iterator[list[dict]]:
    """Stream `gold/reviews` as row-dict batches so peak memory stays O(batch_size)."""
    dataset = DeltaTable(str(_require_gold_reviews())).to_pyarrow_dataset()
    for record_batch in dataset.to_batches(batch_size=batch_size):
        yield record_batch.to_pylist()


def _iter_limited_batches(batch_size: int, limit: int | None) -> Iterator[list[dict]]:
    remaining = limit
    for rows in iter_gold_review_batches(batch_size):
        if remaining is not None:
            if remaining <= 0:
                return
            rows = rows[:remaining]
            remaining -= len(rows)
        yield rows


def read_gold_reviews(limit: int | None = None) -> list[dict]:
    rows: list[dict] = []
    for batch in _iter_limited_batches(get_settings().embedding_batch_size, limit):
        rows.extend(batch)
    return rows


def _usd_per_token() -> float:
    return AZURE_USD_PER_1M_TOKENS / 1_000_000 if get_settings().provider_mode == "azure" else 0.0


def _new_ledger() -> CostLedger:
    # CostLedger's defaults are per-query caps; indexing is bounded by max_embedding_usd instead.
    ledger = CostLedger()
    ledger.max_cost_usd = get_settings().max_embedding_usd
    ledger.max_tokens = sys.maxsize
    return ledger


def _embed_upsert_batch(
    batch: list[Chunk], embedder, store, ledger: CostLedger, usd_per_token: float
) -> int:
    tokens = sum(len(c.text) for c in batch) // CHARS_PER_TOKEN + len(batch)
    # Record (and cap-check) before embedding so a breach never makes the paid call.
    ledger.add(tokens, tokens * usd_per_token)
    for chunk, vector in zip(batch, embedder.embed([c.text for c in batch]), strict=True):
        chunk.embedding = vector
    return store.upsert(batch)


def embed_and_upsert(chunks: list[Chunk]) -> dict:
    """Embed chunks in batches under the embedding cost cap and upsert them (shared by indexers)."""
    embedder = get_embedder()
    store = get_vector_store()
    store.ensure_schema()
    ledger = _new_ledger()
    usd_per_token = _usd_per_token()

    step = get_settings().embedding_batch_size
    indexed = 0
    for start in range(0, len(chunks), step):
        batch = chunks[start : start + step]
        indexed += _embed_upsert_batch(batch, embedder, store, ledger, usd_per_token)
    return {"indexed": indexed, "tokens": ledger.tokens, "usd": ledger.usd}


def index_reviews(limit: int | None = None) -> dict:
    """Stream Gold reviews through embed+upsert; re-runs hit the same ids, so no duplicates."""
    embedder = get_embedder()
    store = get_vector_store()
    store.ensure_schema()
    ledger = _new_ledger()  # one ledger for the whole run keeps the spend cap global
    usd_per_token = _usd_per_token()

    indexed = 0
    for rows in _iter_limited_batches(get_settings().embedding_batch_size, limit):
        batch = [chunk_review(row) for row in rows]
        indexed += _embed_upsert_batch(batch, embedder, store, ledger, usd_per_token)
    return {"indexed": indexed, "tokens": ledger.tokens, "usd": ledger.usd}


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed gold/reviews into the vector store.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="index only the first N reviews (default: all Gold)",
    )
    args = parser.parse_args()
    result = index_reviews(args.limit)
    print(f"indexed={result['indexed']} tokens~{result['tokens']} usd=${result['usd']:.4f}")


if __name__ == "__main__":
    main()


def prepare_candidate_reviews(rows: list[dict], source_snapshot: str) -> tuple[list, list[dict]]:
    """Normalize bounded isolated rows; reject bad identities/text explicitly."""
    from retrieval.chunking import source_parent

    if len(rows) > 100:
        raise ValueError("Candidate fixture is limited to 100 reviews")
    parents, rejected = [], []
    for at, row in enumerate(rows):
        try:
            parents.append(source_parent(row, source_snapshot))
        except ValueError as exc:
            rejected.append({"row": at, "reason": str(exc).splitlines()[0]})
    return parents, rejected
