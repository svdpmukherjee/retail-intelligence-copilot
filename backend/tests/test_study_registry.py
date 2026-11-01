from collections import Counter

import pytest

from eval.study_cost import dollars_for, load_models, models_by_id

REQUIRED = [
    "id",
    "family",
    "tier",
    "slug",
    "license",
    "portability",
    "usd_per_1m_input",
    "usd_per_1m_output",
    "price_source_url",
    "price_checked",
    "price_confidence",
]


def test_registry_has_six_models_balanced_by_tier_and_family():
    models = load_models()
    assert len(models) == 6
    assert Counter(m["tier"] for m in models) == {"small": 2, "medium": 2, "large": 2}
    assert Counter(m["family"] for m in models) == {"google": 3, "mistral": 3}


def test_every_model_has_all_fields_non_empty():
    for m in load_models():
        for field in REQUIRED:
            assert m.get(field) not in (None, ""), (m.get("id"), field)


def test_slugs_and_ids_unique():
    models = load_models()
    assert len({m["slug"] for m in models}) == 6
    assert len(models_by_id()) == 6


def test_prices_are_positive_floats():
    for m in load_models():
        for key in ("usd_per_1m_input", "usd_per_1m_output"):
            assert isinstance(m[key], float) and m[key] > 0


def test_dollars_for_hand_worked():
    model = {"usd_per_1m_input": 1.0, "usd_per_1m_output": 2.0}
    assert dollars_for(model, 1000, 500) == pytest.approx(0.002, abs=1e-12)
    assert dollars_for(model, 0, 0) == 0.0
