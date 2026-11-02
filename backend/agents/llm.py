from typing import Protocol

import httpx

from app.config import Settings, get_settings
from app.cost import CostLedger, LLMCall
from retrieval.embeddings import AZURE_API_VERSION, GoAheadRequired

CHARS_PER_TOKEN = 4


class LLM(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def model(self) -> str: ...

    async def complete(
        self,
        system: str,
        user: str,
        *,
        ledger: CostLedger,
        max_tokens: int | None = None,
        task: str | None = None,
    ) -> str: ...


def estimate_tokens(*texts: str) -> int:
    return sum(len(t) for t in texts) // CHARS_PER_TOKEN + 1


async def _chat(
    url: str, headers: dict[str, str], payload: dict, *, timeout: float = 60
) -> tuple[str, dict | None]:
    """Returns the message content and the provider's `usage` block (None if it sent none)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"], data.get("usage")


def _actual_tokens(
    usage: dict | None, system: str, user: str, limit: int
) -> tuple[int, int, int]:
    """(prompt, completion, total) from the provider's usage, falling back to the chars/4 estimate
    plus the reserved output cap when the provider returns no usage block."""
    if usage:
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        if total:
            return prompt, completion, total
    est = estimate_tokens(system, user)
    return est, limit, est + limit


class FreeLLM:
    """OpenAI-compatible endpoint (e.g. local Ollama); $0. Unconfigured means unavailable."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        s = self._settings
        return bool(s.free_llm_base_url and s.free_llm_model)

    @property
    def model(self) -> str:
        return self._settings.free_llm_model or "free-llm"

    async def complete(
        self,
        system: str,
        user: str,
        *,
        ledger: CostLedger,
        max_tokens: int | None = None,
        task: str | None = None,
    ) -> str:
        s = self._settings
        if not self.available:
            raise RuntimeError("Free LLM not configured; set FREE_LLM_BASE_URL and FREE_LLM_MODEL.")
        limit = max_tokens or s.llm_max_tokens
        reserved = estimate_tokens(system, user) + limit
        ledger.add(reserved, 0.0)
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
        content, usage = await _chat(url, headers, payload)
        p, c, t = _actual_tokens(usage, system, user, limit)
        ledger.settle(reserved, 0.0, LLMCall(self.model, p, c, t, 0.0, task))
        return content


class AzureLLM:
    """Azure OpenAI chat. Gated: refuses without keys + go-ahead flag."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def available(self) -> bool:
        return True

    @property
    def model(self) -> str:
        return self._settings.azure_openai_chat_deployment or "azure-openai"

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
        self,
        system: str,
        user: str,
        *,
        ledger: CostLedger,
        max_tokens: int | None = None,
        task: str | None = None,
    ) -> str:
        endpoint, key, deployment = self._require_go_ahead()
        s = self._settings
        price = s.azure_llm_usd_per_1m_tokens
        limit = max_tokens or s.llm_max_tokens
        # Worst-case reservation: a cap breach raises here, before any paid call.
        reserved = estimate_tokens(system, user) + limit
        reserved_usd = reserved * price / 1_000_000
        ledger.add(reserved, reserved_usd)
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
        content, usage = await _chat(url, {"api-key": key}, payload)
        p, c, t = _actual_tokens(usage, system, user, limit)
        ledger.settle(
            reserved, reserved_usd, LLMCall(deployment, p, c, t, t * price / 1_000_000, task)
        )
        return content


class OpenRouterLLM:
    """OpenRouter chat (OpenAI-compatible, hosted open-weight models). Gated like Azure."""

    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self._settings = settings
        self._model = model or settings.openrouter_model

    @property
    def available(self) -> bool:
        return True

    @property
    def model(self) -> str:
        return self._model or "openrouter"

    def _require_go_ahead(self) -> tuple[str, str, str]:
        s = self._settings
        if not (s.openrouter_go_ahead and s.openrouter_api_key and self._model):
            raise GoAheadRequired(
                "OpenRouter LLM requires human go-ahead: set OPENROUTER_GO_AHEAD=true plus "
                "OPENROUTER_API_KEY and a model (OPENROUTER_MODEL). "
                "Use PROVIDER_MODE=free for $0 runs."
            )
        return (
            f"{s.openrouter_base_url.rstrip('/')}/chat/completions",
            s.openrouter_api_key.get_secret_value(),
            self._model,
        )

    async def complete(
        self,
        system: str,
        user: str,
        *,
        ledger: CostLedger,
        max_tokens: int | None = None,
        task: str | None = None,
    ) -> str:
        url, key, model = self._require_go_ahead()
        s = self._settings
        price = s.openrouter_usd_per_1m_tokens
        limit = max_tokens or s.llm_max_tokens
        # Worst-case reservation: a cap breach raises here, before any paid call.
        reserved = estimate_tokens(system, user) + limit
        reserved_usd = reserved * price / 1_000_000
        ledger.add(reserved, reserved_usd)
        payload = {
            "model": model,
            "max_tokens": limit,
            # OpenRouter echoes real token counts here, so the ledger can settle to actuals.
            "usage": {"include": True},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        content, usage = await _chat(url, {"Authorization": f"Bearer {key}"}, payload)
        p, c, t = _actual_tokens(usage, system, user, limit)
        ledger.settle(reserved, reserved_usd, LLMCall(model, p, c, t, t * price / 1_000_000, task))
        return content


def get_llm(*, model: str | None = None) -> LLM:
    """`model` overrides the OpenRouter slug per client (ignored in other modes) without
    mutating the shared settings singleton."""
    settings = get_settings()
    if settings.provider_mode == "azure":
        return AzureLLM(settings)
    if settings.provider_mode == "openrouter":
        return OpenRouterLLM(settings, model=model)
    return FreeLLM(settings)
