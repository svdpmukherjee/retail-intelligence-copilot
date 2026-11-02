import pytest

from agents import model_policy
from app.config import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, **kw) -> None:
    monkeypatch.setattr(model_policy, "get_settings", lambda: Settings(**kw))


def test_each_task_maps_to_its_tier_model(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(
        monkeypatch,
        openrouter_model="default/model",
        openrouter_model_small="small/model",
        openrouter_model_medium="medium/model",
        openrouter_model_large="large/model",
    )
    # summary -> small, route/compose -> medium, sql -> large (see docs/model-comparison.md).
    assert model_policy.model_for("summary") == "small/model"
    assert model_policy.model_for("route") == "medium/model"
    assert model_policy.model_for("compose") == "medium/model"
    assert model_policy.model_for("sql") == "large/model"


def test_policy_exposes_tier_and_rationale(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, openrouter_model_large="large/model")
    choice = model_policy.policy_for("sql")
    assert choice.task == "sql" and choice.tier == "large" and choice.model == "large/model"
    assert choice.rationale  # a non-empty, auditable reason for the choice


def test_unset_tier_falls_back_to_provider_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # A tier cleared in .env resolves to None, i.e. "use openrouter_model" — never a hard failure.
    _settings(
        monkeypatch,
        openrouter_model="default/model",
        openrouter_model_small=None,
        openrouter_model_medium=None,
        openrouter_model_large=None,
    )
    assert model_policy.model_for("summary") is None
    assert model_policy.model_for("route") is None
    assert model_policy.model_for("sql") is None
