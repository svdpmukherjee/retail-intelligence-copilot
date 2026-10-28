"""Retrieval-quality harness: recall@k and MRR over the gold question -> doc set."""

import json
from pathlib import Path

from app.config import get_settings
from eval.metrics import mean, mrr, recall_at_k
from retrieval.hybrid import hybrid_search
from retrieval.index_docs import index_docs, read_docs
from retrieval.schema import CHUNKS_TABLE
from retrieval.vector_store import PgVectorStore, get_vector_store

GROUND_TRUTH = Path(__file__).parent / "ground_truth" / "retrieval.json"


def ensure_docs_indexed() -> bool:
    """Index the authored docs only if some are absent; True if it indexed (free embedder, $0)."""
    store = get_vector_store()
    if not isinstance(store, PgVectorStore):
        raise RuntimeError("The retrieval harness needs VECTOR_STORE=pgvector (the $0 path).")
    store.ensure_schema()
    with store._connect(vectors=False) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT doc_id FROM {CHUNKS_TABLE} WHERE source_type = 'doc'"
        ).fetchall()
    indexed = {row[0] for row in rows}
    if {doc_id for doc_id, _ in read_docs()} <= indexed:
        return False
    index_docs()
    return True


def _dedupe(doc_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(doc_ids))


def evaluate_retrieval(k: int | None = None) -> dict:
    """Per-question and aggregate recall@k / MRR; reads the existing index (call
    `ensure_docs_indexed` first)."""
    k = get_settings().retrieval_top_k if k is None else k
    cases = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    per_question = []
    for case in cases:
        hits = hybrid_search(case["question"], k, filters={"source_type": "doc"})
        retrieved = _dedupe([h.chunk.doc_id for h in hits if h.chunk.doc_id])
        relevant = case["relevant_doc_ids"]
        per_question.append(
            {
                "question": case["question"],
                "retrieved": retrieved,
                "recall": recall_at_k(retrieved, relevant, k),
                "mrr": mrr(retrieved, relevant),
            }
        )
    return {
        "k": k,
        "recall_at_k": mean([q["recall"] for q in per_question]),
        "mrr": mean([q["mrr"] for q in per_question]),
        "per_question": per_question,
    }
