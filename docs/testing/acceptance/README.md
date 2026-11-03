# Pipeline acceptance & quality testing

> Current status: [answer-quality-status.md](../../answer-quality-status.md).
> `quality-baseline.*`, `quality-stage2.*` and `evidence-stage3.*` are frozen
> historical snapshots. New runs use a new output path; their results may differ
> because conversation contracts changed. Do not overwrite these files to get PASS.

A curated battery of **queries** that validate — with evidence — that every RAG
capability we built (M1–M7) actually works, is accurate, and is reliable, **before**
we move to the end-to-end app (M8). Each query targets a specific capability and has
explicit **pass conditions**; results and our read of them are recorded with evidence.

## What to call this

It is **acceptance & quality testing** of the whole pipeline — UAT-style (human,
scenario/query-driven, evidence + judgement), but broader than one scenario. It sits
alongside the other levels, not instead of them:

| Level | Scope | Here |
|---|---|---|
| Unit | one function, mocked | `backend/tests/` (developer) |
| SIT | components wired + one smoke | `docs/testing/sit.md` (tester) |
| **Acceptance & quality (this folder)** | **the full pipeline, per capability, with evidence** | **human** |
| Evaluation (M7) | automated metric gate (recall@k, MRR, faithfulness, cost, latency) | `backend/eval/` |

## Files

- `../answer-quality-change-proposal.md` — approved option B/stage 1 direction,
  issue inventory, staged plan and A01–A22 expectations.
- `quality-baseline.md` / `quality-baseline.json` — **synthetic** full-pipeline
  contract baseline, separate from live acceptance and existing docs-only CI scores.
- `cases.md` — the catalogue: every test case (capability · query · role · expected ·
  pass conditions).
- `run_acceptance.py` — runs the cases against the live pipeline and prints evidence.
- `RESULTS.md` — the captured run: actual output per case, verdict, and our decisions.

## How to run ($0, free mode)

### Answer-quality regression baseline (stage 1)

From `backend/`, run in a dedicated process:

```bash
.venv/bin/python -m eval.quality_baseline --output /private/tmp/ric-quality-current
```

This uses 12 authored review rows, four categories, the authored return policy,
in-memory DuckDB, bag-of-words retrieval, a scripted LLM and ephemeral memory.
Production routing, query resolution, SQL execution/guard, hybrid fusion, composer
and MemoryManager execute unchanged. No Postgres, hosted calls, model downloads,
indexing, or durable audit/memory writes. Scripted SQL success does not measure
text-to-SQL model quality; synthetic retrieval does not measure real embeddings.
Recorded synthetic timings are not serving latency benchmarks.

Use `--cases A02 A04` for a bounded subset. The runner covers the backend aspects
of A01–A12 for marketing and executive, including original role-specific sequences.
A13–A22 and browser/qualitative-support assertions remain explicitly NOT RUN.
The JSON contains original/resolved questions, decisions, SQL, selected product
IDs, source bodies/metadata and responses. Review support against actual passages;
do not interpret citation reference integrity as faithfulness.

Exit codes: **1** observed failure; **2** incomplete coverage without observed
failure; **0** only complete passing coverage. The committed initial report exits 1
because it records existing defects. This runner is not added to the existing CI
gate, and no old thresholds were relaxed. Case-level FAIL takes precedence over
NOT RUN; a case cannot PASS while any applicable check remains unmeasured.

Optional bounded read-only local probe:

```bash
.venv/bin/python -m eval.quality_baseline --mode live --cases A02 A04 --output /private/tmp/ric-quality-live-baseline
```

Live mode requires existing Gold/pgvector and a configured **keyless loopback free
LLM**. It refuses remote/paid generation, disables audit/tracing persistence, uses
ephemeral conversation storage, and forces offline model loading. It never creates
or repairs corpus/index/schema state. Missing prerequisites produce NOT RUN; runtime
logic errors produce FAIL. Synthetic numeric gold does not apply to live data.
Live artifacts must be outside the repository; existing email/phone redaction is
applied, but proprietary text/other identifiers still require human review before
sharing. The local preflight during stage 1 refused the current provider settings;
no live quality result is claimed.

Hermetic verification, intentionally without the DB-creating shared conftest:

```bash
.venv/bin/python -m pytest --noconftest tests/test_quality_baseline.py tests/test_grounding.py tests/test_eval_metrics.py -q
```

Only these DB-free tests use this invocation; the new suite explicitly forbids
network/Postgres access. Continue using normal isolation for DB-backed suites.

### Existing live acceptance catalogue

```bash
cd backend && source .venv/bin/activate      # uses backend/.env (pgvector + Ollama)
python ../docs/testing/acceptance/run_acceptance.py
```
Prerequisites: pgvector up (`docker compose -f infra/docker-compose.yml up -d`), the
index built (`python -m retrieval.index_reviews && python -m retrieval.index_docs`), and
Ollama running with `llama3.2:3b` for the LLM paths.

## Conditions to check in every result

A generic checklist — read each response's `answer` + `audit` against these:

| # | Condition | Where to look |
|---|---|---|
| C1 | **Routing** — did it pick the right tool for the question type? | `audit.intent` |
| C2 | **Tool path** — SQL for aggregates, retrieval for meaning, both for "why" | `audit.tool_path` |
| C3 | **Grounding** — `path` is `llm` or `extractive`; `issues` empty or a justified block | `audit.grounding` |
| C4 | **Citations** — every claim cited; labels map to real sources; no citation to an unlisted number | `answer`, `citations` |
| C5 | **Access control** — retrieved `sources` stay inside the role's allowed categories; out-of-scope → empty; unknown role → denied | `audit.sources`, errors |
| C6 | **PII** — no raw email/phone/name in the answer; redaction tokens (`[EMAIL]`) where expected | `answer` |
| C7 | **Hybrid** — vector-only and keyword-only rankings differ, and the fused list blends both | retrieval evidence (AC-11) |
| C8 | **Reranking** — with `RERANKER=local`, order/scores change vs `none` | retrieval evidence (AC-12) |
| C9 | **Memory** — `history_turns_used` grows within a thread; preferences recalled across threads | `audit.memory` |
| C10 | **Cost / latency** — `cost_usd` = 0 in free mode; `latency_ms` within a sane bound | `audit` |
| C11 | **Accuracy** — numeric answers match a hand-computed ground truth | `answer` vs known data |

Status legend used in `RESULTS.md`: ✅ pass · ⚠️ pass with caveat · ❌ fail (→ defect).

### Explicitly authorized hosted Stage 1 probe

`eval.hosted_quality_probe` is a separate, opt-in OpenRouter-only wrapper. It keeps
runtime configuration unchanged and uses the real baseline with ephemeral memory,
offline embeddings and no audit/tracing writes. All Postgres connections enforce
read-only transactions. It reads current model prices, retains conservative
reservations across all questions (including failed requests), limits the run to
60 generation attempts and at most $2, and sends provider-side price ceilings.
Unknown/unpriced models and other billing surfaces are refused. These reservations
are conservative bounds, not actual spend; actual cost is reported separately when
the provider supplies it. Finish reasons and request outcomes are journaled locally.

Hosted generation sends questions and retrieved review/document excerpts to
OpenRouter and the selected model providers. Explicit authorization must cover
both this transfer and the spending cap. Output artifacts remaining local does
not mean the inference payload stays on this machine.

After that authorization, from `backend/`:

```bash
.venv/bin/python -m eval.hosted_quality_probe --authorize-hosted --budget-usd 2 --cases A01 A02 A03 A04 A05 A06 --output /private/tmp/ric-quality-hosted-stage1
```

Results include a `.budget.json` journal plus JSON/Markdown observations. Keep all
three outside Git. Budget refusal prevents subsequent requests; it is not a
successful quality result. The original local-only runner remains unchanged.

### Stage 2 comparison (preserves the Stage 1 before baseline)

```bash
.venv/bin/python -m eval.quality_baseline --output /private/tmp/ric-quality-current-stage2
```

`quality-stage2.{json,md}` records 108 passing contract assertions, zero failing
assertions and 66 unmeasured assertions. Case rows remain NOT RUN until all
applicable qualitative/boundary/browser checks are measured; this is not a claim
that live generation quality passed. Keep `quality-baseline.*` unchanged as the
before artifact. Stage 2 verification/limitations are documented in
`docs/modules/M4_answer_quality_stage2.md`.

## Stage 3 evidence foundations (isolated)

Approved scope and operational gates:
`.claude/specs/M3_answer_quality_stage3_proposal.md`.
Artifact `evidence-stage3.{json,md}` records synthetic fixture sources with real
cached embeddings/SQLite FTS/Delta SQL and pipeline checks. It does not replace
`quality-baseline.*`, `quality-stage2.*`, the existing CI gate or semantic review.

From `backend/`, after reading the test fixtures:

```bash
.venv/bin/python -m pytest --noconftest tests/test_evidence_coverage.py tests/test_stage3_evidence.py -q
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false .venv/bin/python -m eval.stage3_evidence_smoke --output /private/tmp/ric-stage3-fixture-smoke.json
```

The smoke ignores serving `.env`, disables generation/audit/memory/tracing, denies
service connections, uses the cached local model, and creates/removes only a
bounded synthetic temporary workspace. It refuses remote embedders and real source
snapshots. Missing cached models must fail plainly; do not download one to obtain PASS.
The optional two-review `data/tests/test_gold_stage3.py` requires existing Java and
explicit `STAGE3_DELTA_JARS` paths; it starts a local Spark JVM and uses only pytest
temporary Silver/Gold directories. Do not run the shared DB-backed suite against
serving data. No real backfill or serving bundle activation is implied.

A read-only coverage CLI is available (`python -m eval.evidence_coverage --output
<outside-repo.json> --trace-asin <product>`). The completed live audit is local at
`/private/tmp/ric-stage3-coverage.json`; it records independent Delta/index snapshots,
not a general retrieval or answer-quality pass.

## Practical source/narration workaround

User-authorized scope: `.claude/specs/M4_answer_quality_stage4_workaround.md`;
implementation and measured limits: `docs/modules/M4_answer_quality_workaround.md`.
Read-only selected-product source lookup does not require re-embedding the corpus.
It does not make general sampled-review retrieval representative.

Focused checks, after inspecting fixtures:

```bash
# backend/; deliberately bypass the shared DB-creating conftest
.venv/bin/python -m pytest --noconftest tests/test_source_review_workaround.py tests/test_answer_truthfulness.py tests/test_stage2_quality.py -q
# frontend/
npm run test:answer-quality
npm run build
```

Live final checks remain local at `/private/tmp/ric-stage4-final-live-check.json`
and `/private/tmp/ric-stage4-browser/`. These used real existing data with generation
disabled and ephemeral chats. Markdown/grouped-reference browser testing used a
separately labelled synthetic API response. Do not interpret it as a factual-support
or hosted-generation pass; do not replace earlier before-baseline artifacts.


## Latest hosted conversation evidence and publication audit

The M4 conversation note records71browser turns/27distinct queries including debug
failures/replays,25named latest-outcome checks and their limits. The live transcripts,
model outputs and screenshots stay local under `/private/tmp/ric-natural-browser/`;
they are not Git artifacts and may disappear. Durable summaries are in
[the current status](../../answer-quality-status.md) and
[conversation note](../../modules/M4_conversational_planning.md).
A separate broader hermetic pre-publication run includes the baseline, hosted-budget,
coverage and Stage3 contracts; its current result is recorded in CURRENT_TASK/WORKLOG.

Snapshot byte hashes are recorded in `snapshot-checksums.json`; verify them before
comparing new reports. The old docs-only CI gate and its thresholds are unchanged.
No citation syntax, synthetic generation, sampled recall or aggregate assertion is a
full semantic-support or overall quality acceptance claim. Publishing does not
approve a serving migration, reindex, paid retest or deployment.
