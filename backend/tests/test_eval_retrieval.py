import pytest

from app.config import Settings
from eval.retrieval_eval import ensure_docs_indexed, evaluate_retrieval


def test_retrieval_metrics_are_bounded_and_some_question_is_fully_recalled() -> None:
    if Settings().database_url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    try:
        ensure_docs_indexed()
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    result = evaluate_retrieval()
    assert 0.0 <= result["recall_at_k"] <= 1.0
    assert 0.0 <= result["mrr"] <= 1.0
    assert any(q["recall"] == 1.0 for q in result["per_question"])
