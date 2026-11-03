# Unit testing (developer-owned)

**Scope:** one function or class in isolation. **Owner:** the `developer`
sub-agent, written and run while building each sub-module.

- Framework: `pytest`; one test file per area (e.g. `tests/test_cost.py`).
- Deterministic and fast; **mock external calls** (Azure, DB, LLM) at this level.
- Cover the contract and its edge cases, not just the happy path.
- Must be green before a sub-module is handed to the tester.

**Example (M1):** `backend/tests/test_cost.py` checks `CostLedger` under the cap,
at the cap, and over the cap (expects `CostCeilingExceeded`).

## Gold data in CI

`test_sql_agent.py` and `test_index_reviews.py` use the `synthetic_gold` fixture
in `backend/tests/conftest.py`. It creates five authored reviews across two
categories as temporary Delta tables and redirects only those tests' Gold paths.
Pytest removes the temporary data under its normal temporary-directory retention
policy. No real reviews, local Gold tables, ETL run or cloud service is needed.
The SQL tests still execute real DuckDB queries; review tests still read real
Delta batches. Database-backed indexing remains a separate integration check
and skips when no database is configured.


## Answer-quality publication checks (2026-11-03)

Read `backend/tests/conftest.py` first: it creates a dedicated `_test` database and
DB-backed suites may DROP tables. Never run those suites on the serving corpus.
The following inspected suites use authored fixtures, fake providers, temporary
immutable bundles and in-memory DuckDB; bypassing conftest is safe **only for this
explicit list**, not arbitrary tests. They need no hosted call or model download.

From the repository root:

```bash
backend/.venv/bin/python -m pytest --noconftest \
  backend/tests/test_natural_conversation.py \
  backend/tests/test_conversation_planning.py \
  backend/tests/test_combined_questions.py \
  backend/tests/test_stage2_quality.py \
  backend/tests/test_composer.py backend/tests/test_router.py \
  backend/tests/test_model_policy.py backend/tests/test_answer_truthfulness.py \
  backend/tests/test_source_review_workaround.py \
  backend/tests/test_evidence_coverage.py backend/tests/test_hosted_quality_probe.py \
  backend/tests/test_quality_baseline.py backend/tests/test_stage3_evidence.py -q
backend/.venv/bin/python -m ruff check backend
backend/.venv/bin/python -m black --check backend
npm --prefix frontend run test:answer-quality
npm --prefix frontend run build
```

These checks verify contracts, not hosted semantic quality. The publication run
passed **177 tests**; details: [publication-verification.md](publication-verification.md). No full local
DB-backed pytest/CI eval run is claimed; CI uses its own isolated database. The
optional Spark Stage3 test needs existing Java/cached jars and temporary paths;
do not start Spark/download jars just for a documentation audit.

Before comparing snapshots, verify SHA256 values in
`docs/testing/acceptance/snapshot-checksums.json`. Run new baseline observations to
new temporary output paths, never the frozen before-baseline. If live reruns are
requested, confirm current budget, transfer approval and fixtures; use read-only
connections and ephemeral chats. Old approval does not authorize arbitrary paid work.
