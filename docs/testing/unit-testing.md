# Unit testing (developer-owned)

**Scope:** one function or class in isolation. **Owner:** the `developer`
sub-agent, written and run while building each sub-module.

- Framework: `pytest`; one test file per area (e.g. `tests/test_cost.py`).
- Deterministic and fast; **mock external calls** (Azure, DB, LLM) at this level.
- Cover the contract and its edge cases, not just the happy path.
- Must be green before a sub-module is handed to the tester.

**Example (M1):** `backend/tests/test_cost.py` checks `CostLedger` under the cap,
at the cap, and over the cap (expects `CostCeilingExceeded`).
