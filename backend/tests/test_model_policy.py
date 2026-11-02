import pytest

from agents import model_policy
from app.config import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, **kw) -> None:
    monkeypatch.setattr(model_policy, "get_settings", lambda: Settings(**kw))


def test_lightweight_tasks_use_fast_tier_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, openrouter_model="big/model", openrouter_model_fast="small/model")
    assert model_policy.model_for("route") == "small/model"
    assert model_policy.model_for("summary") == "small/model"


def test_reasoning_tasks_always_use_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, openrouter_model="big/model", openrouter_model_fast="small/model")
    # None means "provider default": compose/sql stay on the strong model.
    assert model_policy.model_for("compose") is None
    assert model_policy.model_for("sql") is None


def test_no_fast_model_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, openrouter_model="big/model")
    assert model_policy.model_for("route") is None
    assert model_policy.model_for("summary") is None
