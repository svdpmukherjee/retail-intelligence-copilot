from app.config import get_settings


class CostCeilingExceeded(Exception):
    """Raised when an entry would push spend past a configured cap."""


class CostLedger:
    """Accumulates tokens and USD for one query/run and enforces the caps.

    A breaching entry is rejected *before* it is recorded, so totals never
    exceed the caps and the caller can still report what was actually spent.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.max_cost_usd = settings.max_cost_usd
        self.max_tokens = settings.max_tokens_per_query
        self.tokens = 0
        self.usd = 0.0

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
