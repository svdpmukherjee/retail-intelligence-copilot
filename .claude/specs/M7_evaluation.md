# Spec M7: Evaluation (metrics harness + CI gate)

## User story
As an engineer evolving the copilot, I want an automated evaluation harness that
measures retrieval quality, answer quality, cost, and latency against a small
version-controlled ground-truth set and fails the CI build when any metric
regresses past a configured threshold, so that a change that quietly degrades
recall, faithfulness, cost, or latency cannot be merged. It runs in free
provider mode at $0 with no cloud credentials; the Azure LLM-judge is gated like
every other Azure seam.

## Module intent & integration with what exists
M7 adds `backend/eval/` (PRD §11; `eval` is already in `pyproject` packages) and
**reuses existing seams only — no new infra, no re-run of ETL or embedding**:
- Retrieval metrics run gold questions through M4 `retrieval.hybrid.hybrid_search`
  (pinned `source_type="doc"` like `docs_rag`) over the existing pgvector `chunks`
  index; a retrieved `SearchHit.chunk.doc_id` is matched against gold `doc_id`s.
  `doc_id` is the authored-doc relative path sans suffix (e.g.
  `authored/return-refund-policy`, `manuals/smart-speaker-user-manual`), exactly
  as `retrieval.index_docs.read_docs` produces it.
- Answer/cost/latency metrics run gold questions through `agents.pipeline.answer`
  and read the already-emitted `result.audit` fields `cost_usd`, `latency_ms`,
  `tokens`, `grounding`, plus `AnswerResult.answer`/`.citations`. No change to
  `pipeline.answer` or the M6 `audit_log` schema.
- The judge rides the existing LLM adapter (`agents.llm.get_llm`): the default
  **deterministic** judge runs at $0; the Azure LLM-judge is reached only in
  `provider_mode="azure"` with `azure_llm_go_ahead=true` (the existing gate), so
  CI needs no cloud credentials.
- Spend is bounded by the existing `CostLedger` cap (`max_cost_usd`); in free
  mode spend is $0.

## Module acceptance criteria
- [ ] `python -m eval.run_eval` runs the four-dimension eval over the committed
      ground-truth set and exits **0** when every metric meets its threshold and
      **non-zero** when any metric regresses past `backend/eval/thresholds.json`.
- [ ] All four PRD §8 dimensions are reported: retrieval `recall@k` + `MRR`
      (labelled Q→doc set over authored docs), answer `faithfulness`/accuracy
      (judge vs ground-truth), `cost_per_query_usd`, and latency `p50`/`p95` ms.
- [ ] The whole gate runs in `provider_mode="free"` at **$0**, deterministically,
      with only a local pgvector (no Azure, no hosted LLM). The Azure LLM-judge is
      gated behind `azure_llm_go_ahead` and never invoked in the $0 path.
- [ ] Thresholds are config-driven (edit `thresholds.json`, no code change) and
      the gate is wired as a GitHub Actions job under `.github/workflows/`.
- [ ] Ground-truth fixtures are tiny, authored, and version-controlled (per
      `.claude/rules/testing.md`); no ETL or embedding is re-run by the gate.
- [ ] `ruff`/`black` clean on `backend/eval/` and all changed files.

## Sub-modules (ordered, each build → verify → integrate)

### M7.1 Metric primitives + ground-truth fixtures
- Goal: pure, DB-free metric functions and the small labelled datasets they score.
- Acceptance criteria:
  - [ ] `backend/eval/metrics.py` exports `recall_at_k(retrieved, relevant, k)`,
        `mrr(retrieved, relevant)`, `percentile(values, p)` (p50/p95), and
        `mean(values)`; each is a pure function with deterministic output and a
        unit test (no DB, no network).
  - [ ] `backend/eval/ground_truth/retrieval.json` holds ~8–12 items
        `{"question": ..., "relevant_doc_ids": ["authored/..."]}` whose doc_ids all
        exist under `data/docs/`; `backend/eval/ground_truth/answers.json` holds
        the same questions with `{"question", "role", "must_include": [keywords],
        "relevant_doc_ids": [...]}` for faithfulness scoring. Questions are
        docs-RAG answerable at $0 (no SQL/LLM-only questions in the $0 set).
  - [ ] A test asserts every gold `doc_id` is a real file under `data/docs/` (keeps
        fixtures honest).
- Build steps:
  1. `backend/eval/__init__.py`, `backend/eval/metrics.py` (pure functions).
  2. Author `ground_truth/retrieval.json` and `ground_truth/answers.json` from the
     authored corpus (policies/manuals give trustworthy Q→doc/Q→A pairs).
  3. `backend/tests/test_eval_metrics.py`: unit-test each metric on hand-worked
     cases + the fixture-integrity check.
- Files to touch: `backend/eval/__init__.py`, `backend/eval/metrics.py`,
  `backend/eval/ground_truth/retrieval.json`, `backend/eval/ground_truth/answers.json`,
  `backend/tests/test_eval_metrics.py`.
- Integration point: standalone; downstream sub-modules import these functions and
  datasets. No existing code changes.

### M7.2 Retrieval-quality harness (recall@k, MRR)
- Goal: score retrieval over the real `chunks` index using the gold Q→doc set.
- Acceptance criteria:
  - [ ] `backend/eval/retrieval_eval.py::evaluate_retrieval(k=None)` runs each gold
        question through `hybrid_search(q, k, filters={"source_type": "doc"})`,
        maps hit `chunk.doc_id`s to the retrieved doc list, and returns per-question
        + aggregate `recall@k` and `MRR` (k defaults to `settings.retrieval_top_k`).
  - [ ] It does **not** embed or re-index at import; it reads the existing index. A
        tiny idempotent `ensure_docs_indexed()` helper calls M3 `index_docs()` once
        if the docs are absent (free embedder, $0) so the harness is self-contained
        in CI, then queries.
  - [ ] A test asserts aggregate recall@k and MRR are in `[0, 1]` and recall is 1.0
        for at least one question whose answer doc is unambiguous; **skip-with-reason**
        if pgvector is unreachable (per `testing.md`), never a silent pass.
- Build steps:
  1. `backend/eval/retrieval_eval.py`: load `retrieval.json`, call `hybrid_search`,
     dedupe retrieved `doc_id`s preserving rank, compute metrics via `metrics.py`.
  2. `ensure_docs_indexed()` reusing `retrieval.index_docs.index_docs` (idempotent
     upsert already exists); no review re-embed needed for doc recall.
  3. `backend/tests/test_eval_retrieval.py` (live pgvector; skip-with-reason if down).
- Files to touch: `backend/eval/retrieval_eval.py`,
  `backend/tests/test_eval_retrieval.py`.
- Integration point: consumes M4 `hybrid_search` + the M3 `chunks` index and
  `index_docs`; pins `source_type="doc"` exactly as `docs_rag` does.

### M7.3 Answer-quality harness + per-query cost/latency capture
- Goal: judge grounded answers against ground-truth and capture cost/latency per
  query from the audit record, at $0 by default with the Azure judge gated.
- Acceptance criteria:
  - [ ] `backend/eval/answer_eval.py::evaluate_answers()` runs each gold question
        through `pipeline.answer(q, role=...)` and, for each, records a
        `faithfulness`/accuracy score from a **judge** plus `cost_usd`,
        `latency_ms`, `tokens` read from `result.audit`.
  - [ ] Default judge is deterministic and $0: scores an answer on (a) every claim
        line carrying a resolvable citation (reuse `governance.grounding`/`audit`
        `grounding` signal — a grounded cited answer scores high, an ungrounded one
        low) and (b) coverage of the gold `must_include` keywords. The LLM judge
        (`get_llm().complete`, CostLedger-wrapped) is selected only when
        `eval_judge="llm"`, and Azure stays gated behind `azure_llm_go_ahead`
        (raises `GoAheadRequired` if not granted) — the $0 path never calls it.
  - [ ] A test asserts the deterministic judge gives a high score to a known-good
        grounded answer and a low score to a stub ungrounded/empty-evidence answer;
        cost in free mode is `0.0`. Skip-with-reason if pgvector is unreachable.
- Build steps:
  1. `backend/eval/answer_eval.py`: `judge_deterministic(answer, citations, grounding,
     must_include)`, an optional `judge_llm(...)` behind `get_llm()`, and
     `evaluate_answers()` that assembles per-query `{faithfulness, cost_usd,
     latency_ms, tokens}` records.
  2. Add `eval_judge: Literal["deterministic","llm"] = "deterministic"` to
     `Settings` (default $0); the LLM judge reuses the existing `azure_llm_go_ahead`
     gate via `get_llm()`.
  3. `backend/tests/test_eval_answer.py` (live pgvector; skip-with-reason if down).
- Files to touch: `backend/eval/answer_eval.py`, `backend/app/config.py`,
  `backend/.env.example`, `backend/tests/test_eval_answer.py`.
- Integration point: consumes `pipeline.answer` + its `audit` dict (M4/M6) and the
  `get_llm()` adapter; introduces no new field on the pipeline.

### M7.4 CI gate runner + thresholds + GitHub Actions wiring
- Goal: one command that aggregates all four dimensions, compares to config
  thresholds, exits non-zero on regression, and runs as a CI job at $0.
- Acceptance criteria:
  - [ ] `backend/eval/thresholds.json` holds config-driven gates: `min_recall_at_k`,
        `min_mrr`, `min_faithfulness`, `max_cost_per_query_usd`, `max_latency_p50_ms`,
        `max_latency_p95_ms` (latency caps set generously for CI variance, with a
        warm-up query before timing so model-load time is excluded).
  - [ ] `python -m eval.run_eval` runs M7.2 + M7.3 over the shared query set,
        aggregates (recall@k, MRR, mean faithfulness, mean cost/query, p50/p95
        latency via `metrics.py`), prints a per-dimension pass/fail report, and
        exits **0** if all pass, **non-zero** (naming the breaching metric) if any
        regresses. It honours `provider_mode="free"` / no cloud creds.
  - [ ] A test drives the gate end to end: with lenient thresholds it exits 0; with
        a deliberately impossible threshold it exits non-zero and names the metric.
  - [ ] `.github/workflows/` runs the gate as a job that provisions a pgvector
        `services:` container, installs backend, and runs `python -m eval.run_eval`
        in free mode — green and $0 with no secrets.
- Build steps:
  1. `backend/eval/thresholds.json` + a loader in `run_eval.py`.
  2. `backend/eval/run_eval.py` (`__main__`): run both harnesses once, aggregate,
     compare to thresholds, print report, `sys.exit(0/1)`.
  3. `backend/tests/test_eval_gate.py`: pass-case + fail-case on thresholds.
  4. Add an `eval` job to `.github/workflows/ci.yml` (or new `eval.yml`) with a
     `pgvector/pgvector:pg16` service, `DATABASE_URL=postgresql://rag:rag@localhost:5432/rag`,
     `PROVIDER_MODE=free`, `pip install -e .`, then `python -m eval.run_eval`.
- Files to touch: `backend/eval/thresholds.json`, `backend/eval/run_eval.py`,
  `backend/tests/test_eval_gate.py`, `.github/workflows/ci.yml`.
- Integration point: ties M7.1–M7.3 into one runnable gate; the CI job mirrors the
  existing backend job’s setup, adding the pgvector service the live path needs.

## Test plan
- Per sub-module (scoped): M7.1 metric functions on hand-worked cases + fixture
  integrity (no DB); M7.2 recall@k/MRR in `[0,1]` with ≥1 recall=1.0 against the
  live index (skip-with-reason if DB down); M7.3 deterministic judge scores a
  grounded answer high / ungrounded low and cost=0 in free mode; M7.4 the gate
  exits 0 under lenient thresholds and non-zero (naming the metric) under an
  impossible one.
- Module-level end-to-end smoke (one real, non-mocked check; free mode, local
  pgvector, no hosted LLM): run `python -m eval.run_eval`; assert it indexes the
  authored docs idempotently, reports all four dimensions, writes the report, and
  exits 0 with `cost_per_query_usd == 0.0`. This is the heavy eval gate the Tester
  runs live (`.claude/rules/testing.md`).

## Security & cost notes
- **Expected cloud spend for M7 = $0; cap = $0 in CI.** The gate runs in free mode
  (free embedder + deterministic judge + extractive composer), deterministically,
  with only local pgvector. **CHECKPOINT 1 is also the cost go-ahead** and
  authorises only this $0 evaluation layer. The Azure LLM-judge path (`eval_judge="llm"`
  in `provider_mode="azure"`) is gated behind the existing `azure_llm_go_ahead`
  flag and `CostLedger`; it is never reached in the $0 gate and its use would be a
  separate, logged (`COST.md`) go-ahead.
- No secrets introduced; CI needs no cloud credentials. Ground-truth fixtures are
  authored and committed (no PII, no raw data); the gate reads the existing index
  and never re-runs ETL or paid embedding.

## Out of scope
- SQL-agent / text-to-SQL answer quality in the $0 gate (SQL needs an LLM; those
  questions are excluded from the free-mode set — evaluable only under an Azure
  go-ahead later).
- A trend/quality dashboard or historical metric storage beyond the printed report
  and the existing `audit_log` rows — M8/M9.
- Changing `pipeline.answer`, the `audit` dict, the `audit_log` schema, retrieval,
  or memory behaviour — M7 only measures them.
- Tuning retrieval/prompts to hit thresholds — the harness measures; tuning is a
  separate change via `/change`.
