import asyncio
from datetime import date

import pytest

from app.config import Settings
from eval import report, study
from eval.study_cost import load_models
from retrieval.embeddings import GoAheadRequired


def _sample(models: list[dict]) -> dict:
    rows = [
        {
            **{k: m[k] for k in study.STATIC_KEYS},
            "id": m["id"],
            "faithfulness": 0.5,
            "grounded_path_rate": 1.0,
            "citation_validity_rate": 1.0,
            "routing_accuracy": 0.25,
            "latency_p50_ms": 100.0,
            "latency_p95_ms": 200.0,
            "dollars_per_query": 0.0001,
            "tokens": 10,
        }
        for m in models
    ]
    sql = [{"model": m["id"], "question": "q", "sql": "", "runnable": False} for m in models]
    return {"models": rows, "sql": sql}


def test_render_report_has_sections_and_one_row_per_model(tmp_path):
    models = load_models()
    path = report.render_report(
        _sample(models), dry_run=True, models=models, path=tmp_path / "r.md", today=date(2026, 1, 1)
    )
    text = path.read_text()
    for header in ("## Results", "## Descriptive SQL", "## Methodology", "## Models & pricing"):
        assert header in text
    assert "DRY-RUN" in text and "2503" in text and "ground_truth" in text
    for m in models:
        assert f"| {m['id']} | {m['tier']} |" in text


def test_render_report_marks_live_run(tmp_path):
    models = load_models()
    path = report.render_report(
        _sample(models), dry_run=False, models=models, path=tmp_path / "r.md"
    )
    assert "Real gated run" in path.read_text() and "DRY-RUN" not in path.read_text()


def test_estimate_is_positive_with_per_model_breakdown():
    models = load_models()
    est = report.estimate_spend(models)
    assert set(est["per_model"]) == {m["id"] for m in models} and len(models) == 6
    assert all(v > 0 for v in est["per_model"].values())
    assert est["total"] == pytest.approx(sum(est["per_model"].values()))
    assert est["calls"] == 22 * 6


def test_live_run_refused_without_go_ahead(tmp_path, monkeypatch):
    cost = tmp_path / "COST.md"
    cost.write_text("| a |\n")
    monkeypatch.setattr(
        study, "get_settings", lambda: Settings(_env_file=None, provider_mode="openrouter")
    )
    with pytest.raises(GoAheadRequired):
        study._require_go_ahead()
    code = asyncio.run(study.execute(live=True, report_path=tmp_path / "r.md", cost_path=cost))
    assert code == 2 and cost.read_text() == "| a |\n" and not (tmp_path / "r.md").exists()


def test_dry_run_writes_report_without_paid_call_or_cost_line(tmp_path, monkeypatch):
    cost = tmp_path / "COST.md"
    cost.write_text("| a |\n")
    seen = {}

    async def fake_run(models, *, dry_run=False):
        seen["dry_run"] = dry_run
        return _sample(models)

    monkeypatch.setattr(study, "run_study", fake_run)
    code = asyncio.run(study.execute(live=False, report_path=tmp_path / "r.md", cost_path=cost))
    assert code == 0 and seen["dry_run"] is True
    assert "DRY-RUN" in (tmp_path / "r.md").read_text()
    assert cost.read_text() == "| a |\n"


def test_log_spend_appends_row_to_cost_table(tmp_path):
    cost = tmp_path / "COST.md"
    cost.write_text("# C\n\n| h |\n|---|\n| row |\n\ntext\n")
    actual = study.log_spend({"models": [{"dollars_per_query": 0.001}]}, 0.5, cost)
    lines = cost.read_text().splitlines()
    assert actual == pytest.approx(0.01)
    assert lines[5].startswith("|") and "B-8" in lines[5] and lines[6] == ""
