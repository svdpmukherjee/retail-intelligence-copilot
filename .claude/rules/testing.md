# Testing

- Framework: `pytest`. Tests are small, deterministic, and named for the
  behaviour they check.
- **At least one real end-to-end check per data/LLM path**, not only mocks. A
  mocked suite can pass while the real Azure/DB/retrieval path is broken. For a
  retrieval or answer path, run a live query and assert a grounded, cited result.
- Retrieval quality and answer quality have an **evaluation gate** (recall@k /
  MRR; faithfulness; cost/query; p50/p95 latency). The gate runs in CI and fails
  the build on regression beyond thresholds.
- If a live check cannot run (missing key/quota), the Tester reports that
  plainly — it is not a silent PASS.
- Keep fixtures tiny; the authored policy/manual docs provide ground-truth
  question→answer pairs for evaluation. See **Fixture performance & isolation**.

## Testing levels (who owns what)

| Level | Owner | What |
|---|---|---|
| **Unit** | developer | one function/class in isolation; mocks external calls. See `docs/testing/unit-testing.md` |
| **SIT** (system integration) | tester | components wired together + one real end-to-end smoke at the module boundary. See `docs/testing/sit.md` |
| **UAT** (acceptance) | human | approval against the spec's acceptance criteria at CHECKPOINT 2; scenarios + findings logged in `docs/testing/uat.md` and `docs/testing/uat-log.md` |
| **Evaluation** | M6 only | retrieval/answer quality + cost/latency gate |

SIT is deliberately **lightweight** here — a glimpse of enterprise practice that
proves the module's components interact correctly, enough to call the module
complete. It is not a multi-environment test campaign.

## Fixture performance & isolation

DB-backed tests must stay fast and isolated. A test suite that re-embeds the real
corpus per test is neither (it cost ~40 min once — 2026-11-01). Rules:

- **Index a small bounded slice, never the full corpus.** Build-time indexing
  (`index_reviews()`) in a test always passes an explicit bound — prefer the
  **gold sample** (the curated ground-truth rows the retrieval assertions use),
  or an explicit `limit=` — so the fixture embeds tens of rows, not the whole DB.
  Full-corpus indexing belongs to the build/ETL step, not the test suite.
- **Build the expensive, read-only corpus once per session.** A fixture that
  creates+indexes `chunks` is `scope="session"` and must not be mutated by tests.
- **Reset mutable per-test state per test.** Tables tests *write* to (`messages`,
  `threads`, `user_memory`) are truncated by a **function-scoped** fixture so no
  state leaks between tests. Never fold these into the session-scoped index
  fixture — a shared index is fine, shared conversation memory is cross-test
  contamination.
- Isolation still routes through `conftest.py` to the `<db>_test` database
  (fails closed); these rules change *speed and scope*, never the DB target.
