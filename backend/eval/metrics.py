"""Pure, deterministic metric primitives for the evaluation harness."""

import math
from collections.abc import Sequence


def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """Fraction of relevant ids found in the top-k retrieved ids (0.0 if nothing is relevant)."""
    gold = set(relevant)
    if not gold:
        return 0.0
    return len(gold & set(retrieved[:k])) / len(gold)


def mrr(retrieved: Sequence[str], relevant: Sequence[str]) -> float:
    """Reciprocal rank of the first relevant id (0.0 if none is retrieved)."""
    gold = set(relevant)
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in gold:
            return 1 / rank
    return 0.0


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile, p in [0, 100]; 0.0 for an empty sequence."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return float(ordered[rank - 1])


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sequence."""
    return sum(values) / len(values) if values else 0.0
