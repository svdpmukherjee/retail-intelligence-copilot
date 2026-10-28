import pytest

from app import cost
from app.config import Settings
from app.cost import CostCeilingExceeded, CostLedger


@pytest.fixture(autouse=True)
def small_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cost,
        "get_settings",
        lambda: Settings(max_cost_usd=1.0, max_tokens_per_query=100),
    )


def test_under_cap_accumulates() -> None:
    ledger = CostLedger()
    ledger.add(40, 0.25)
    ledger.add(30, 0.25)
    assert ledger.tokens == 70
    assert ledger.usd == pytest.approx(0.5)


def test_usd_over_cap_raises_and_is_not_recorded() -> None:
    ledger = CostLedger()
    ledger.add(10, 0.9)
    with pytest.raises(CostCeilingExceeded):
        ledger.add(10, 0.2)
    assert ledger.usd == pytest.approx(0.9)


def test_token_over_cap_raises() -> None:
    ledger = CostLedger()
    with pytest.raises(CostCeilingExceeded):
        ledger.add(101, 0.0)
