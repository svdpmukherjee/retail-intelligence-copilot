"""Budget and mutation guards, with no provider or database calls."""

import json
from unittest.mock import patch

import pytest

from app.config import Settings
from eval.hosted_quality_probe import Budget, ProbeLimit, authorized_probe, main


def payload():
    return {"model": "test", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 512}


def test_budget_is_run_wide_and_retains_failed_reservations():
    budget = Budget({"test": (0.0001, 0.0001)}, 0.75)
    budget.reserve(payload())
    with pytest.raises(ProbeLimit):
        budget.reserve(payload())
    assert budget.report()["requests"] == 1
    assert budget.report()["reserved_upper_usd"] < 1


def test_call_limit_and_unpriced_models_fail_before_request():
    budget = Budget({"test": (0, 0)}, 2, max_calls=1)
    with pytest.raises(ProbeLimit):
        budget.reserve({**payload(), "model": "unknown"})
    budget.reserve(payload())
    with pytest.raises(ProbeLimit):
        budget.reserve(payload())
    for cap in [0, -1, 2.01, float("nan")]:
        with pytest.raises(ValueError):
            Budget({}, cap)


def test_readonly_connections_are_enforced_and_patches_restored(tmp_path):
    import psycopg

    from eval import quality_baseline

    settings = Settings.model_construct(
        provider_mode="openrouter",
        openrouter_go_ahead=True,
        openrouter_api_key="private",
        database_url="private",
    )
    with patch.object(psycopg, "connect") as connection:
        original = psycopg.connect
        with authorized_probe(settings, Budget({}, 2), tmp_path / "budget.json"):
            psycopg.connect("private", options="-c default_transaction_read_only=off")
            assert "default_transaction_read_only=on" in connection.call_args.kwargs["options"]
        assert psycopg.connect is original
    assert quality_baseline.live_prerequisites(settings)


def test_explicit_authorization_and_outside_repo_artifact_required():
    with pytest.raises(SystemExit):
        main(["--budget-usd", "2", "--output", "/private/tmp/test-quality"])
    with pytest.raises(SystemExit):
        main(["--authorize-hosted", "--budget-usd", "2", "--output", __file__])


def test_guarded_request_reserves_before_io_and_sets_price_ceiling(tmp_path):
    import asyncio

    import httpx

    from agents import llm

    settings = Settings.model_construct(
        provider_mode="openrouter",
        openrouter_go_ahead=True,
        openrouter_api_key="private",
        database_url="private",
    )
    budget = Budget({"test": (0.0000001, 0.0000002)}, 2)
    journal = tmp_path / "budget.json"

    async def response(request):
        assert json.loads(journal.read_text())["requests"] == 1
        body = json.loads(request.content)
        assert body["provider"]["max_price"]["prompt"] == pytest.approx(0.1)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}, "finish_reason": "length"}],
                "usage": {"cost": 0.00001},
            },
        )

    original_client = httpx.AsyncClient
    with patch.object(
        httpx,
        "AsyncClient",
        side_effect=lambda **kw: original_client(transport=httpx.MockTransport(response), **kw),
    ):
        with authorized_probe(settings, budget, journal):
            answer, _ = asyncio.run(
                llm._chat(settings.openrouter_base_url + "/chat/completions", {}, payload())
            )
    assert answer == "ok"
    assert budget.calls[0]["finish_reason"] == "length"
    assert budget.report()["provider_reported_usd"] == 0.00001
