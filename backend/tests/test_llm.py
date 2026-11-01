import asyncio

import httpx
import pytest

from agents import llm as llm_mod
from agents.llm import AzureLLM, FreeLLM, OpenRouterLLM, get_llm
from app import cost
from app.config import Settings
from app.cost import CostCeilingExceeded, CostLedger
from retrieval.embeddings import GoAheadRequired

AZURE = dict(
    azure_openai_endpoint="https://x.openai.azure.com/",
    azure_openai_api_key="k",
    azure_openai_chat_deployment="chat",
)


@pytest.fixture(autouse=True)
def caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cost, "get_settings", lambda: Settings(max_cost_usd=1.0, max_tokens_per_query=1000)
    )


@pytest.fixture
def fake_post(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def post(self, url, **kwargs):
        calls.append(url)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return calls


def test_get_llm_free_mode_unconfigured_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_mod, "get_settings", lambda: Settings(provider_mode="free"))
    llm = get_llm()
    assert isinstance(llm, FreeLLM)
    assert llm.available is False


def test_get_llm_azure_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_mod, "get_settings", lambda: Settings(provider_mode="azure"))
    assert isinstance(get_llm(), AzureLLM)


def test_free_complete_records_zero_usd(fake_post: list[str]) -> None:
    llm = FreeLLM(Settings(free_llm_base_url="http://localhost:11434/v1", free_llm_model="m"))
    ledger = CostLedger()
    assert asyncio.run(llm.complete("sys", "user", ledger=ledger, max_tokens=100)) == "hi"
    assert fake_post == ["http://localhost:11434/v1/chat/completions"]
    assert ledger.tokens > 100
    assert ledger.usd == 0.0


def test_azure_without_go_ahead_raises_and_makes_no_call(fake_post: list[str]) -> None:
    llm = AzureLLM(Settings(**AZURE))
    with pytest.raises(GoAheadRequired):
        asyncio.run(llm.complete("s", "u", ledger=CostLedger(), max_tokens=10))
    assert fake_post == []


def test_azure_records_estimated_cost(fake_post: list[str]) -> None:
    llm = AzureLLM(Settings(azure_llm_go_ahead=True, azure_llm_usd_per_1m_tokens=2.0, **AZURE))
    ledger = CostLedger()
    asyncio.run(llm.complete("s", "u", ledger=ledger, max_tokens=100))
    assert len(fake_post) == 1
    assert ledger.tokens > 0
    assert ledger.usd == pytest.approx(ledger.tokens * 2.0 / 1_000_000)


def test_cap_breach_refuses_before_paid_call(fake_post: list[str]) -> None:
    llm = AzureLLM(Settings(azure_llm_go_ahead=True, **AZURE))
    ledger = CostLedger()
    with pytest.raises(CostCeilingExceeded):
        asyncio.run(llm.complete("s", "u", ledger=ledger, max_tokens=5000))
    assert fake_post == []
    assert ledger.tokens == 0


OPENROUTER = dict(openrouter_api_key="k", openrouter_model="vendor/model-a")


def test_openrouter_without_go_ahead_or_key_raises_and_makes_no_call(fake_post: list[str]) -> None:
    for settings in (Settings(**OPENROUTER), Settings(openrouter_go_ahead=True)):
        with pytest.raises(GoAheadRequired):
            asyncio.run(OpenRouterLLM(settings).complete("s", "u", ledger=CostLedger()))
    assert fake_post == []


def test_openrouter_without_model_raises(fake_post: list[str]) -> None:
    llm = OpenRouterLLM(Settings(openrouter_go_ahead=True, openrouter_api_key="k"))
    with pytest.raises(GoAheadRequired):
        asyncio.run(llm.complete("s", "u", ledger=CostLedger()))
    assert fake_post == []


def test_openrouter_posts_bearer_and_model_with_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    async def post(self, url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hi"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    llm = OpenRouterLLM(
        Settings(openrouter_go_ahead=True, openrouter_usd_per_1m_tokens=2.0, **OPENROUTER)
    )
    ledger = CostLedger()
    assert asyncio.run(llm.complete("s", "u", ledger=ledger, max_tokens=100)) == "hi"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["headers"] == {"Authorization": "Bearer k"}
    assert seen["json"]["model"] == "vendor/model-a"
    assert ledger.usd == pytest.approx(ledger.tokens * 2.0 / 1_000_000)


def test_openrouter_reserves_ledger_before_call(fake_post: list[str]) -> None:
    llm = OpenRouterLLM(Settings(openrouter_go_ahead=True, **OPENROUTER))
    ledger = CostLedger()
    with pytest.raises(CostCeilingExceeded):
        asyncio.run(llm.complete("s", "u", ledger=ledger, max_tokens=5000))
    assert fake_post == []
    assert ledger.tokens == 0


def test_get_llm_model_override_is_per_client_and_does_not_mutate_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(provider_mode="openrouter", **OPENROUTER)
    monkeypatch.setattr(llm_mod, "get_settings", lambda: settings)
    default, other = get_llm(), get_llm(model="vendor/model-b")
    assert isinstance(other, OpenRouterLLM)
    assert (default._model, other._model) == ("vendor/model-a", "vendor/model-b")
    assert settings.openrouter_model == "vendor/model-a"


def test_openrouter_mode_pairs_with_free_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    from retrieval import embeddings

    monkeypatch.setattr(embeddings, "get_settings", lambda: Settings(provider_mode="openrouter"))
    assert isinstance(embeddings.get_embedder(), embeddings.FreeEmbedder)
