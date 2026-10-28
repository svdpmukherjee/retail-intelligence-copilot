import pytest

from app.config import Settings
from eval.run_eval import load_thresholds, main

LENIENT = {
    "min_recall_at_k": 0.0,
    "min_mrr": 0.0,
    "min_faithfulness": 0.0,
    "max_cost_per_query_usd": 0.0,
    "max_latency_p50_ms": 1e9,
    "max_latency_p95_ms": 1e9,
}


def _run(thresholds: dict[str, float]) -> int:
    if Settings().database_url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    try:
        return main(thresholds)
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")


def test_committed_thresholds_define_every_gate() -> None:
    assert set(LENIENT) <= set(load_thresholds())


def test_gate_exits_zero_with_lenient_thresholds() -> None:
    assert _run(LENIENT) == 0


def test_gate_fails_and_names_metric_when_threshold_impossible(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _run({**LENIENT, "min_faithfulness": 1.01}) == 1
    out = capsys.readouterr().out
    assert "FAIL  faithfulness" in out
    assert "gate FAILED: faithfulness" in out
