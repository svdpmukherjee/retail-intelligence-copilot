"""Hermetic M7 baseline verification: deliberately independent of DB pytest fixtures."""

import asyncio
import json
import socket
from unittest.mock import patch

import pytest

from agents import pipeline, router
from agents.composer import AnswerResult
from app import config
from eval import quality_baseline as baseline
from eval.quality_fixture import load_fixture


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("Hermetic baseline test attempted external I/O")

    monkeypatch.setattr("psycopg.connect", refused)
    monkeypatch.setattr(socket.socket, "connect", refused)


def result(tools, *, sql=None, citations=None):
    return AnswerResult(
        answer="Fixture output", citations=citations or [], sql=sql, audit={"tool_path": tools}
    )


def status(checks, name):
    return next(c["status"] for c in checks if c["name"] == name)


def test_catalogue_has_sequences_roles_boundaries_and_independent_gold():
    catalogue, fixture = baseline.load_catalogue(), load_fixture()
    assert [c["id"] for c in catalogue["cases"]] == [f"A{i:02}" for i in range(1, 13)]
    assert [c["id"] for c in catalogue["boundaries"]] == [f"A{i:02}" for i in range(13, 23)]
    assert catalogue["roles"] == ["marketing", "executive"]
    assert catalogue["cases"][2]["setup"] == [catalogue["cases"][1]["question"]]
    for category, expected in fixture["averages"].items():
        values = [r["rating"] for r in fixture["rows"] if r["category"] == category]
        assert sum(values) / len(values) == expected
    for category, ids in fixture["lowest"].items():
        groups = {}
        for row in fixture["rows"]:
            if row["category"] == category:
                groups.setdefault(row["asin"], []).append(row["rating"])
        eligible = {key: sum(v) / len(v) for key, v in groups.items() if len(v) >= 2}
        assert [min(eligible, key=eligible.get)] == ids


def test_numeric_oracle_rejects_runnable_but_wrong_averages():
    case, fixture = baseline.load_catalogue()["cases"][1], load_fixture()
    observation = {
        "resolved_query": case["question"],
        "retrieved": [],
        "sql": {
            "columns": ["category", "avg_rating"],
            "rows": [[k, v] for k, v in fixture["averages"].items()],
        },
    }
    good = baseline.assess(
        case, "executive", observation, result(["sql_agent"]), fixture, "fixture", []
    )
    assert status(good, "numeric gold") == "PASS"
    observation["sql"]["rows"][0][1] = 1.234
    bad = baseline.assess(
        case, "executive", observation, result(["sql_agent"]), fixture, "fixture", []
    )
    assert status(bad, "numeric gold") == "FAIL"


def test_product_join_rejects_other_product_even_in_correct_category():
    case, fixture = baseline.load_catalogue()["cases"][3], load_fixture()
    observation = {
        "resolved_query": case["question"],
        "sql": {"columns": ["asin", "avg_rating"], "rows": [["E-low", 1.0]]},
        "retrieved": [{"source_type": "review", "category": "Electronics", "asin": "E-high"}],
    }
    checks = baseline.assess(
        case, "marketing", observation, result(["sql_agent", "review_rag"]), fixture, "fixture", []
    )
    assert status(checks, "requested category") == "PASS"
    assert status(checks, "selected product gold") == "PASS"
    assert status(checks, "product evidence join") == "FAIL"


def test_scope_oracle_rejects_unauthorized_source():
    case = baseline.load_catalogue()["cases"][0]
    observation = {
        "resolved_query": case["question"],
        "sql": None,
        "retrieved": [{"source_type": "review", "category": "Books", "asin": "K-good"}],
    }
    checks = baseline.assess(
        case, "marketing", observation, result(["review_rag"]), load_fixture(), "fixture", []
    )
    assert status(checks, "observable scope") == "FAIL"


def test_standalone_oracle_rejects_inherited_topic():
    case = baseline.load_catalogue()["cases"][2]
    observation = {
        "resolved_query": case["setup"][0] + " " + case["question"],
        "retrieved": [],
        "sql": None,
    }
    checks = baseline.assess(
        case, "executive", observation, result([]), load_fixture(), "fixture", []
    )
    assert status(checks, "standalone query") == "FAIL"


def test_fixture_runs_real_pipeline_and_restores_adapters_without_persistence():
    original_route, original_settings = pipeline.route, config.get_settings
    with patch.object(pipeline, "record_audit", side_effect=AssertionError("Audit write")):
        report = asyncio.run(baseline.run(case_ids={"A02", "A03", "A04", "A10", "A12"}))
    assert pipeline.route is original_route
    assert config.get_settings is original_settings
    rows = {(r["id"], r["role"]): r for r in report["results"]}
    for role in ("marketing", "executive"):
        averages = rows[("A02", role)]
        assert status(averages["checks"], "numeric gold") == "PASS"
        assert averages["observation"]["sql"]["rows"]
        assert averages["response"]["audit"]["cost_usd"] == 0
        sequence = rows[("A03", role)]
        assert sequence["response"]["audit"]["memory"]["history_turns_used"] == (
            4 if role == "marketing" else 2
        )
        assert sequence["setup"][-1]["question"].startswith("What's the average")
        assert rows[("A12", role)]["setup"][0]["kind"] == "clarification"
        assert status(rows[("A12", role)]["checks"], "clarification resolved") == "PASS"
        for row in (r for r in rows.values() if r["role"] == role):
            assert "response" in row  # Harness exceptions must not hide as missing coverage.
            assert status(row["checks"], "qualitative support") == "NOT RUN"
            assert status(row["checks"], "live generation and retrieval") == "NOT RUN"
    assert report["mode"] == "fixture"
    assert "Synthetic" in baseline.markdown(report)
    assert all(r["status"] != "PASS" for r in report["results"])


def test_execution_exception_is_failure_and_preserves_partial_observation():
    with patch.object(router, "derive_scope", side_effect=ValueError("sensitive error")):
        report = asyncio.run(baseline.run(case_ids={"A02"}))
    assert all(r["status"] == "FAIL" for r in report["results"])
    assert all(r["observation"]["resolved_query"] for r in report["results"])
    assert "sensitive error" not in json.dumps(report)
    assert baseline.exit_code(report) == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"provider_mode": "openrouter"},
        {"free_llm_base_url": "https://example.com/v1", "free_llm_model": "x"},
        {
            "free_llm_base_url": "http://127.0.0.1/v1",
            "free_llm_model": "x",
            "free_llm_api_key": "secret",
        },
    ],
)
def test_live_configuration_refuses_paid_remote_or_keyed_endpoints(updates):
    settings = config.Settings.model_construct(**updates)
    assert baseline.live_prerequisites(settings)


def test_blocked_live_run_does_not_call_pipeline_or_report_pass(monkeypatch):
    settings = config.Settings.model_construct()
    monkeypatch.setattr(config, "Settings", lambda: settings)
    with patch.object(pipeline, "answer", side_effect=AssertionError("Provider called")):
        report = asyncio.run(baseline.run("live", {"A02"}))
    assert report["summary"] == {"PASS": 0, "FAIL": 0, "NOT RUN": 2}
    assert baseline.exit_code(report) == 2


def test_live_artifacts_cannot_be_written_in_repo(tmp_path):
    with pytest.raises(SystemExit) as exc:
        baseline.main(["--mode", "live", "--output", str(baseline.CASES.parent / "live")])
    assert exc.value.code == 2


def test_cli_writes_evidence_and_boundary_not_run(tmp_path):
    output = tmp_path / "report"
    code = baseline.main(["--cases", "A02", "A13", "--output", str(output)])
    report = json.loads(output.with_suffix(".json").read_text())
    assert code == 2  # Numeric checks pass; live/manual coverage remains unavailable.
    assert report["results"][-1]["id"] == "A13"
    assert report["results"][-1]["status"] == "NOT RUN"
    assert report["results"][0]["observation"]["sql"]["sql"].startswith("SELECT")
    assert "No aggregate faithfulness" in output.with_suffix(".md").read_text()


def test_status_precedence_and_redacted_artifacts():
    checks = [baseline.check("a", True, "ok"), baseline.check("b", None, "unavailable")]
    assert baseline.verdict(checks) == "NOT RUN"
    checks.append(baseline.check("c", False, "wrong"))
    assert baseline.verdict(checks) == "FAIL"
    assert baseline.scrub({"text": "Contact person@example.com"}) == {"text": "Contact [EMAIL]"}
    report = {"results": [{"status": "PASS"}]}
    assert baseline.exit_code(report) == 0
    report["results"].append({"status": "NOT RUN"})
    assert baseline.exit_code(report) == 2
    report["results"].append({"status": "FAIL"})
    assert baseline.exit_code(report) == 1


def test_unknown_case_rejected_before_pipeline_execution():
    with pytest.raises(ValueError, match="Unknown"):
        asyncio.run(baseline.run(case_ids={"A99"}))


def test_context_cleanup_on_failure():
    original = pipeline.route
    with pytest.raises(RuntimeError), baseline.capture():
        raise RuntimeError("aborted")
    assert pipeline.route is original


def test_live_missing_model_or_database_is_not_run_but_logic_errors_fail(monkeypatch):
    settings = config.Settings.model_construct()
    monkeypatch.setattr(config, "Settings", lambda: settings)
    monkeypatch.setattr(baseline, "live_prerequisites", lambda _: None)
    for error, expected in [
        (FileNotFoundError("private path"), "NOT RUN"),
        (ValueError("private detail"), "FAIL"),
    ]:
        with patch.object(pipeline, "answer", side_effect=error):
            report = asyncio.run(baseline.run("live", {"A02"}))
        assert all(row["status"] == expected for row in report["results"])
        assert "private" not in json.dumps(report)
