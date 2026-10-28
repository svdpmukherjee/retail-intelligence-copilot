import asyncio

import pytest

from agents.composer import Citation
from app.config import Settings
from eval.answer_eval import evaluate_answers, judge_deterministic
from eval.retrieval_eval import ensure_docs_indexed

GOOD = "Electronics can be returned within 15 days of delivery. [1]"
CITES = [Citation(n=1, source_id="authored/return-refund-policy#0", label="Return policy")]


def test_judge_scores_grounded_answer_high_and_ungrounded_low() -> None:
    high = judge_deterministic(GOOD, CITES, {"path": "extractive", "issues": []}, ["15 days"])
    stub = "No supporting evidence was found for this question."
    low = judge_deterministic(stub, [], {"path": "none", "issues": []}, ["15 days"])
    assert high == 1.0
    assert low == 0.0


def test_live_answers_are_judged_and_free_mode_costs_nothing() -> None:
    if Settings().database_url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    try:
        ensure_docs_indexed()
        result = asyncio.run(evaluate_answers())
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")
    scores = [q["faithfulness"] for q in result["per_question"]]
    print("faithfulness:", result["faithfulness"], scores)
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert max(scores) >= 0.75
    assert result["cost_per_query_usd"] == 0.0
    assert all(q["latency_ms"] > 0 for q in result["per_question"] if "error" not in q)
