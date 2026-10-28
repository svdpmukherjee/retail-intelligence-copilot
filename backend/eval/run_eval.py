"""CI evaluation gate: run retrieval + answer harnesses once, compare to thresholds, exit 0/1."""

import asyncio
import json
import sys
from pathlib import Path

from eval.answer_eval import answer_docs, evaluate_answers
from eval.metrics import mean, percentile
from eval.retrieval_eval import ensure_docs_indexed, evaluate_retrieval

THRESHOLDS = Path(__file__).parent / "thresholds.json"
WARMUP_QUESTION = "What is the return window for electronics?"
# metric -> (threshold key, True if the metric must be >= threshold, else <=)
GATES = {
    "recall_at_k": ("min_recall_at_k", True),
    "mrr": ("min_mrr", True),
    "faithfulness": ("min_faithfulness", True),
    "cost_per_query_usd": ("max_cost_per_query_usd", False),
    "latency_p50_ms": ("max_latency_p50_ms", False),
    "latency_p95_ms": ("max_latency_p95_ms", False),
}


def load_thresholds(path: Path = THRESHOLDS) -> dict[str, float]:
    return json.loads(path.read_text(encoding="utf-8"))


async def collect() -> dict[str, float]:
    """Run both harnesses once and aggregate the six gated metrics."""
    ensure_docs_indexed()
    # Warm-up loads the embedder so model-load time is not counted as query latency.
    await answer_docs(WARMUP_QUESTION, role="analyst")
    retrieval = evaluate_retrieval()
    answers = await evaluate_answers()
    rows = [q for q in answers["per_question"] if "error" not in q]
    latencies = [q["latency_ms"] for q in rows]
    return {
        "recall_at_k": retrieval["recall_at_k"],
        "mrr": retrieval["mrr"],
        "faithfulness": answers["faithfulness"],
        "cost_per_query_usd": mean([q["cost_usd"] + q["judge_cost_usd"] for q in rows]),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
    }


def check(metrics: dict[str, float], thresholds: dict[str, float]) -> list[str]:
    """Print the per-dimension report; return the names of breaching metrics."""
    breaches = []
    for metric, (key, is_min) in GATES.items():
        value, limit = metrics[metric], thresholds[key]
        ok = value >= limit if is_min else value <= limit
        print(f"{'PASS' if ok else 'FAIL'}  {metric:<20} {value:.4f}  ({key} {limit})")
        if not ok:
            breaches.append(metric)
    return breaches


def main(thresholds: dict[str, float] | None = None) -> int:
    metrics = asyncio.run(collect())
    breaches = check(metrics, load_thresholds() if thresholds is None else thresholds)
    if breaches:
        print(f"Evaluation gate FAILED: {', '.join(breaches)}")
        return 1
    print("Evaluation gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
