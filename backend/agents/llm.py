from typing import Protocol

import httpx

from app.config import Settings, get_settings
from app.cost import CostLedger
from retrieval.embeddings import AZURE_API_VERSION, GoAheadRequired

CHARS_PER_TOKEN = 4


class LLM(Protocol):
    @property
    def available(self) -> bool: ...

    async def complete(
        self, system: str, user: str, *, ledger: CostLedger, max_tokens: int | None = None
    ) -> str: ...


def estimate_tokens(*texts: str) -> int:
    return sum(len(t) for t in texts) // CHARS_PER_TOKEN + 1


async def _chat(url: str, headers: dict[str, str], payload: dict, *, timeout: float = 60) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


class FreeLLM:
    """OpenAI-compatible endpoint (e.g. local Ollama); $0. Unconfigured means unavailable."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        s = self._settings
        return bool(s.free_llm_base_url and s.free_llm_model)

    async def complete(
        self, system: str, user: str, *, ledger: CostLedger, max_tokens: int | None = None
    ) -> str:
        s = self._settings
        if not self.available:
            raise RuntimeError("Free LLM not configured; set FREE_LLM_BASE_URL and FREE_LLM_MODEL.")
        limit = max_tokens or s.llm_max_tokens
        ledger.add(estimate_tokens(system, user) + limit, 0.0)
        headers = {}
        if s.free_llm_api_key:
            headers["Authorization"] = f"Bearer {s.free_llm_api_key.get_secret_value()}"
        payload = {
            "model": s.free_llm_model,
            "max_tokens": limit,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        url = f"{s.free_llm_base_url.rstrip('/')}/chat/completions"
        return await _chat(url, headers, payload)


class AzureLLM:
    """Azure OpenAI chat. Gated: refuses without keys + go-ahead flag."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        return True

    def _require_go_ahead(self) -> tuple[str, str, str]:
        s = self._settings
        if not (
            s.azure_llm_go_ahead
            and s.azure_openai_endpoint
            and s.azure_openai_api_key
            and s.azure_openai_chat_deployment
        ):
            raise GoAheadRequired(
                "Azure LLM requires human go-ahead: set AZURE_LLM_GO_AHEAD=true plus "
                "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY and AZURE_OPENAI_CHAT_DEPLOYMENT. "
                "Use PROVIDER_MODE=free for $0 runs."
            )
        return (
            s.azure_openai_endpoint.rstrip("/"),
            s.azure_openai_api_key.get_secret_value(),
            s.azure_openai_chat_deployment,
        )

    async def complete(
        self, system: str, user: str, *, ledger: CostLedger, max_tokens: int | None = None
    ) -> str:
        endpoint, key, deployment = self._require_go_ahead()
        s = self._settings
        limit = max_tokens or s.llm_max_tokens
        # Worst-case reservation: a cap breach raises here, before any paid call.
        tokens = estimate_tokens(system, user) + limit
        ledger.add(tokens, tokens * s.azure_llm_usd_per_1m_tokens / 1_000_000)
        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={AZURE_API_VERSION}"
        )
        payload = {
            "max_tokens": limit,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        return await _chat(url, {"api-key": key}, payload)


def get_llm() -> LLM:
    settings = get_settings()
    if settings.provider_mode == "azure":
        return AzureLLM(settings)
    return FreeLLM(settings)
