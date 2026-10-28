import argparse
import sys
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


def read_gold_reviews(limit: int | None = None) -> list[dict]:
    path = gold_reviews_path()
    if not path.exists():
        raise FileNotFoundError(f"Gold reviews not found at {path}; run the M2 pipeline first.")
    rows = DeltaTable(str(path)).to_pyarrow_table().to_pylist()
    return rows[:limit] if limit is not None else rows


def embed_and_upsert(chunks: list[Chunk]) -> dict:
    """Embed chunks in batches under the embedding cost cap and upsert them (shared by indexers)."""
    settings = get_settings()
    embedder = get_embedder()
    store = get_vector_store()
    store.ensure_schema()

    # CostLedger's defaults are per-query caps; indexing is bounded by max_embedding_usd instead.
    ledger = CostLedger()
    ledger.max_cost_usd = settings.max_embedding_usd
    ledger.max_tokens = sys.maxsize
    usd_per_token = (
        AZURE_USD_PER_1M_TOKENS / 1_000_000 if settings.provider_mode == "azure" else 0.0
    )

    step = settings.embedding_batch_size
    indexed = 0
    for start in range(0, len(chunks), step):
        batch = chunks[start : start + step]
        tokens = sum(len(c.text) for c in batch) // CHARS_PER_TOKEN + len(batch)
        # Record (and cap-check) before embedding so a breach never makes the paid call.
        ledger.add(tokens, tokens * usd_per_token)
        for chunk, vector in zip(batch, embedder.embed([c.text for c in batch]), strict=True):
            chunk.embedding = vector
        indexed += store.upsert(batch)
    return {"indexed": indexed, "tokens": ledger.tokens, "usd": ledger.usd}


def index_reviews(limit: int | None = None) -> dict:
    """Embed Gold reviews and upsert them; re-runs hit the same ids, so no duplicates."""
    return embed_and_upsert([chunk_review(row) for row in read_gold_reviews(limit)])


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
