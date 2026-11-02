from dataclasses import asdict, dataclass

from app.config import get_settings


class CostCeilingExceeded(Exception):
    """Raised when an entry would push spend past a configured cap."""


@dataclass
class LLMCall:
    """One chat completion's *actual* usage, for the audit + observability planes.

    `model` is the slug/deployment that served the call; token fields come from the provider's
    `usage` block when it returns one, or the chars/4 estimate when it does not. `task` is the
    pipeline step the call served (route / sql / compose / summary), so the audit + observability
    planes can explain which model ran where, and why (see agents.model_policy).
    """

    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    usd: float
    task: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class CostLedger:
    """Accumulates tokens and USD for one query/run and enforces the caps.

    A breaching entry is rejected *before* it is recorded, so totals never exceed the caps and the
    caller can still report what was actually spent. An LLM call reserves its worst case up front
    (so a cap breach is caught before any paid request), then `settle`s to the provider's real
    usage once the response is in — so the recorded totals are actuals, not the reservation.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.max_cost_usd = settings.max_cost_usd
        self.max_tokens = settings.max_tokens_per_query
        self.tokens = 0
        self.usd = 0.0
        self.llm_calls: list[LLMCall] = []

    def add(self, tokens: int, usd: float) -> None:
        if self.tokens + tokens > self.max_tokens:
            raise CostCeilingExceeded(
                f"token cap {self.max_tokens} exceeded ({self.tokens + tokens})"
            )
        if self.usd + usd > self.max_cost_usd:
            raise CostCeilingExceeded(
                f"cost cap ${self.max_cost_usd:.2f} exceeded (${self.usd + usd:.4f})"
            )
        self.tokens += tokens
        self.usd += usd

    def settle(self, reserved_tokens: int, reserved_usd: float, call: LLMCall) -> None:
        """Swap a worst-case reservation for the call's actual usage and record the breakdown.

        Caps were already enforced by the reservation; the call has happened, so this reconciles
        the totals (usually downward) rather than re-checking a cap. Totals never go negative.
        """
        self.tokens = max(0, self.tokens - reserved_tokens + call.total_tokens)
        self.usd = max(0.0, self.usd - reserved_usd + call.usd)
        self.llm_calls.append(call)

    @property
    def models(self) -> list[str]:
        """Distinct model slugs that served this run, in first-use order."""
        return list(dict.fromkeys(c.model for c in self.llm_calls))
