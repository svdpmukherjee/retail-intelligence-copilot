"""Model-study registry and pure $/query helper (no network, no DB)."""

import json
from pathlib import Path

MODELS_FILE = Path(__file__).parent / "ground_truth" / "models.json"


def load_models() -> list[dict]:
    return json.loads(MODELS_FILE.read_text())


def models_by_id() -> dict[str, dict]:
    return {m["id"]: m for m in load_models()}


def dollars_for(model: dict, in_tokens: int, out_tokens: int) -> float:
    """Cost of one call from actual token usage x the model's per-1M-token rates."""
    return (
        in_tokens * model["usd_per_1m_input"] / 1e6 + out_tokens * model["usd_per_1m_output"] / 1e6
    )
