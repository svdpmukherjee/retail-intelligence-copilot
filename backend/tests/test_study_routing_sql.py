import asyncio

import pytest

from agents.sql_agent import gold_structured_path
from eval import study
from eval.study_cost import load_models


def _run(models: list[dict]) -> dict:
    # Routing/SQL sub-runs only; skip the DB-backed answer pass, which test_study_runner covers.
    async def go() -> dict:
        llm = study.DryRunLLM()
        return {
            "acc": [await study._routing_accuracy(llm) for _ in models],
            "sql": [r for m in models for r in await study._sql_rows(m, llm)],
        }

    return asyncio.run(go())


def test_routing_accuracy_is_a_rate_and_cases_miss_the_rules() -> None:
    import json

    from agents.router import _rule_intent

    cases = json.loads(study.ROUTING_SET.read_text(encoding="utf-8"))
    assert all(_rule_intent(c["question"]) is None for c in cases)
    out = _run(load_models()[:2])
    assert len(out["acc"]) == 2
    assert all(0.0 <= a <= 1.0 for a in out["acc"])


def test_sql_rows_have_question_sql_runnable() -> None:
    if not gold_structured_path().exists():
        pytest.skip("Gold structured table not built; run the M2 pipeline to exercise SQL rows")
    models = load_models()[:2]
    rows = _run(models)["sql"]
    assert rows and {r["model"] for r in rows} == {m["id"] for m in models}
    for r in rows:
        assert set(r) == {"model", "question", "sql", "runnable"}
        assert isinstance(r["sql"], str) and isinstance(r["runnable"], bool)
