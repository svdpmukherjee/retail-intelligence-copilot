import asyncio

import pytest

from app.config import Settings, get_settings
from eval import study
from eval.retrieval_eval import ensure_docs_indexed
from eval.study_cost import load_models
from retrieval.embeddings import GoAheadRequired

EXPECTED = {
    "id",
    "slug",
    "family",
    "tier",
    "license",
    "portability",
    "faithfulness",
    "grounded_path_rate",
    "citation_validity_rate",
    "latency_p50_ms",
    "latency_p95_ms",
    "dollars_per_query",
    "tokens",
    "routing_accuracy",
}


class FakeLLM(study.DryRunLLM):
    """Stub standing in for a hosted client; records that it was the one used."""

    calls = 0

    async def complete(self, system, user, *, ledger, max_tokens=None, task=None):
        FakeLLM.calls += 1
        return await super().complete(system, user, ledger=ledger, max_tokens=max_tokens)


@pytest.fixture(scope="module")
def docs_ready() -> None:
    if Settings().database_url is None:
        pytest.skip("DATABASE_URL not set; start infra/docker-compose.yml to run pgvector tests")
    try:
        ensure_docs_indexed()
    except Exception as exc:  # unreachable DB or missing pgvector extension
        pytest.skip(f"pgvector Postgres not reachable: {type(exc).__name__}")


def _check_rows(rows: list[dict], models: list[dict]) -> None:
    assert [r["id"] for r in rows] == [m["id"] for m in models]
    for row in rows:
        assert set(row) == EXPECTED
        for key in ("faithfulness", "grounded_path_rate", "citation_validity_rate"):
            assert 0.0 <= row[key] <= 1.0
        assert 0.0 <= row["latency_p50_ms"] <= row["latency_p95_ms"]
        assert row["dollars_per_query"] >= 0.0 and row["tokens"] >= 0


def test_stubbed_llm_rows_have_shape_and_price_map_dollars(docs_ready, monkeypatch) -> None:
    models = load_models()[:2]
    FakeLLM.calls = 0
    slugs: list[str] = []
    monkeypatch.setattr(study, "get_llm", lambda *, model=None: slugs.append(model) or FakeLLM())
    monkeypatch.setattr(get_settings(), "provider_mode", "free")
    rows = asyncio.run(study.run_study(models))["models"]
    _check_rows(rows, models)
    assert slugs == [m["slug"] for m in models]  # per-model client, selected by registry slug
    assert FakeLLM.calls > 0
    for row in rows:
        assert row["faithfulness"] > 0 and row["grounded_path_rate"] > 0
        # Stub charges $0 itself, so dollars are purely the registry price-map math.
        assert row["tokens"] >= get_settings().llm_max_tokens
        assert row["dollars_per_query"] > 0


def test_dry_run_builds_no_hosted_client(docs_ready, monkeypatch) -> None:
    def boom(**_):
        raise AssertionError("dry run must not build a hosted client")

    monkeypatch.setattr(study, "get_llm", boom)
    models = load_models()[:2]
    rows = asyncio.run(study.run_study(models, dry_run=True))["models"]
    _check_rows(rows, models)


def test_live_run_refuses_without_go_ahead(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "provider_mode", "openrouter")
    monkeypatch.setattr(settings, "openrouter_go_ahead", False)
    with pytest.raises(GoAheadRequired):
        asyncio.run(study.run_study(load_models()[:1]))


def test_citation_validity_flags_dangling_marker_unlike_grounded_rate() -> None:
    assert study._citation_validity("Returns take 30 days. [1]", {1, 2}) == 1.0
    assert study._citation_validity("Returns take 30 days. [3]", {1, 2}) == 0.0
    assert study._citation_validity("Unsupported prose.", {1}) == 0.0
    assert study._citation_validity("No evidence found.", set()) == 1.0
