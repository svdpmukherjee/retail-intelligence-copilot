"""Task-aware model routing, grounded in the B-8 model-comparison study.

An industry copilot does not send every call to its biggest model. Each pipeline task is mapped to
a capability *tier* (small / medium / large), and the tier to a configured model slug — choosing
the model the study measured as best-fit for that task rather than simply the largest. The choice
*and its rationale* are recorded per call, so the audit + observability planes can show not just
which model served each step but why.

`model_for` returns the slug to use, or ``None`` meaning "use the provider default" (so free/azure
modes, which ignore the per-call override, are unaffected, and OpenRouter falls back to
``openrouter_model`` whenever the task's tier is left unset).
"""

from dataclasses import dataclass
from typing import Literal, get_args

from app.config import get_settings

Task = Literal["route", "sql", "compose", "summary"]
Tier = Literal["small", "medium", "large"]
TASKS: tuple[str, ...] = get_args(Task)


@dataclass(frozen=True)
class ModelChoice:
    """The resolved routing decision for one task — surfaced to the operator planes."""

    task: Task
    tier: Tier
    model: str | None  # resolved slug, or None => provider default (openrouter_model)
    rationale: str


# task -> (tier, why). Each rationale cites the measured B-8 result (docs/model-comparison.md,
# 2026-11-01) that justifies the tier, so "why this model" is auditable, not a guess.
_POLICY: dict[str, tuple[Tier, str]] = {
    "summary": (
        "small",
        "Summarising a prior turn for memory is low-stakes; the small tier scored faithfulness "
        "1.00 at the lowest latency and cost.",
    ),
    "route": (
        "medium",
        "Intent classification is a short, structured task; the medium tier lifts routing "
        "accuracy to 0.88 (small 0.75) for a fraction more cost.",
    ),
    "compose": (
        "medium",
        "The synthesised answer the user reads must be faithful and fully cited; the medium tier "
        "scored faithfulness 1.00 and citation validity 1.00 — above the large tier — at lower "
        "cost.",
    ),
    "sql": (
        "large",
        "Text-to-SQL must be exact; the large tier led routing accuracy (1.00) with 4/4 runnable "
        "SQL, so a mis-specified query is least likely.",
    ),
}

_TIER_SETTING: dict[Tier, str] = {
    "small": "openrouter_model_small",
    "medium": "openrouter_model_medium",
    "large": "openrouter_model_large",
}


def policy_for(task: Task) -> ModelChoice:
    """The tier, resolved model slug (or None) and rationale for `task`."""
    tier, rationale = _POLICY[task]
    model = getattr(get_settings(), _TIER_SETTING[tier]) or None
    return ModelChoice(task=task, tier=tier, model=model, rationale=rationale)


def model_for(task: Task) -> str | None:
    """The OpenRouter slug for `task`, or None to use the provider default (openrouter_model)."""
    return policy_for(task).model
