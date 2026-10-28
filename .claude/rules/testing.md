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
  question→answer pairs for evaluation.

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
