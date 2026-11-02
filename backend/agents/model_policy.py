"""Complexity-based model routing.

An industry copilot does not send every call to its biggest model. Lightweight, structured tasks
(classifying intent, summarising a turn for memory) go to a cheaper/faster model; the reasoning
that the user actually reads — synthesising the answer, writing SQL — goes to the strong default.

`model_for` returns the slug to use, or ``None`` meaning "use the provider default" (so free/azure
modes, which ignore the per-call override, are unaffected, and OpenRouter falls back to
``openrouter_model`` whenever no fast model is configured). The chosen model is recorded per call
in the cost ledger, so the audit + observability planes show which model served each step.
"""

from typing import Literal

from app.config import get_settings

Task = Literal["route", "sql", "compose", "summary"]

# Tasks cheap enough to run on the fast tier when one is configured.
_FAST_TASKS: frozenset[str] = frozenset({"route", "summary"})


def model_for(task: Task) -> str | None:
    """The OpenRouter slug for `task`, or None to use the provider default (strong) model."""
    settings = get_settings()
    if task in _FAST_TASKS and settings.openrouter_model_fast:
        return settings.openrouter_model_fast
    return None
