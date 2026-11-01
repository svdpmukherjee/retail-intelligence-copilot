# BACKLOG.md — deferred engineering/UX work

Items parked deliberately, to be picked up **after the cloud data-pipeline
operationalization** (Azure + Databricks) is complete. Each has symptom → root
cause → fix → where, so it can be run the usual command-driven way without
re-deriving context. Pure cosmetic/visual polish lives in `design/BACKLOG.md`;
this file is behaviour + UX correctness.

Found during live verification of the M8 v3 build (support role, two-turn
conversation: "What is the return policy?" → "why?"), 2026-10-29.

## B-1 — Vague follow-up ("why?") false-routes to `sql_rag` — MEDIUM — ❌ DROPPED (resolved) 2026-11-01

> **Dropped — root cause no longer exists.** The `sql_rag` rule in `router.py` already
> requires `\bwhy\b` **paired with** a change-word (`chang|drop|increas|decreas|declin|
> fell|fall|rose|rise|spik|dip`), from the D-2 rule-first routing work — so a bare "why?"
> matches **no** rule and never routes to `sql_rag`. The specific false-route is fixed.
> The residual symptom (a bare "why?" gives a useless answer because the free path has no
> history awareness) is **B-2's** territory, not a routing bug. See `context/BACKLOG_PLAN.md`.

- **Symptom:** a bare "why?" follow-up routed to `sql_rag`, the SQL query failed
  (degraded gracefully), and it answered from an irrelevant Electronics review —
  a useless answer to what was a follow-up about the return policy.
- **Root cause:** the D-2 rule-first router matches the "why-changed → `sql_rag`"
  keyword pattern on a bare "why?", which is a false positive (that rule is for
  "why did sentiment/volume change?").
- **Fix:** tighten the rule so "why" only routes to `sql_rag` when paired with a
  change/trend word (change, increase, drop, trend, more, fewer, …), not on a
  bare "why?". Run as a `/change` (routing-rule revision).
- **Where:** `route()` keyword patterns in `backend/agents/router.py`.

## B-2 — Follow-ups don't use conversation history on the free path — HIGH

- **Symptom:** the thread is stored and now *displayed* (v3), but a vague
  follow-up ("why?") is routed and answered on the bare word, with no awareness
  of the previous turn.
- **Root cause:** documented M5 decision — "in pure free mode the rule-based
  router and extractive composer don't yet *use* loaded history." Memory
  influences only the LLM path.
- **Fix:** on the free path, prepend recent turns to the router/composer input so
  a vague follow-up inherits prior intent/subject. NOTE: M5 deliberately kept
  memory off the free path, so this is a real design decision, not just a patch —
  run as a `/change`. The fuller, more honest fix is the **Azure LLM path**, where
  the router can disambiguate "why?" against context; revisit this item *after*
  operationalization when the stronger model is live.
- **Where:** `backend/agents/router.py`, `backend/agents/composer.py`, memory
  context wiring (M5 `context` kwarg).

## B-3 — Support-shape per-line tag ("FIX"/"ISSUE") mislabels content — MEDIUM

- **Symptom:** every return-policy extract was tagged `FIX`; the review line in
  turn 2 was tagged `ISSUE`. Policy statements are not "fixes" — the tag is
  confusing to a recruiter reading the demo.
- **Root cause:** the support role shape assigns an `ISSUE`/`FIX`/`POLICY` tag per
  answer line via a heuristic that is unreliable on extractive/doc content.
- **Fix:** either make the tag reliable (only tag when the classification is
  confident) or drop the per-line tag and keep the "Governing policy" callout,
  which reads correctly. A UI fix — can fold into a v3 follow-up or a `/change`.
- **Where:** the v3 support-shape component under `frontend/src/components/`.

## B-4 — Citation snippet truncates mid-word — LOW

- **Symptom:** citation [3] ended "…eligible only for a partial re" — severed
  mid-word, no ellipsis.
- **Fix:** truncate snippets on a word boundary and append "…".
- **Where (re-pointed 2026-11-01):** snippets are now produced **server-side** in
  `backend/agents/composer.py` `_snippet()` (`redact(" ".join(text.split())[:MAX_QUOTE_CHARS])`),
  since M8 v2 moved redacted snippets to the backend — fix the word-boundary truncate there.
  `frontend/src/components/EvidencePanel.tsx` only *displays* `shown.snippet` (no change needed).

---

# Retrieval sharpness + model-evaluation batch (added 2026-11-01)

Surfaced while taking the app back to the **local** build and preparing a controlled
model-evaluation study for the portfolio. These are independent of the (now de-scoped)
cloud operationalization — all run on the local stack. Run each as a `/change` (clarify →
weigh options → decide → log ADR → edit spec → rebuild the affected sub-module), then let
the evaluation gate measure the before/after. **Live priority order + parallel-track / conflict
map: `context/BACKLOG_PLAN.md`** (the Product Owner's blueprint — re-run `/prioritize` if the
backlog changes). Wave 1 (B-5, B-6, B-7) is **done + merged 2026-11-01**; next is the full-corpus
embed (data-op P4), then Wave 2 = B-8 (needs B-7) ‖ B-10.

## B-5 — No ANN index on the vector store; search is brute-force — HIGH — ✅ DONE 2026-11-01 (`095328f`)

> **Done.** HNSW index `chunks_embedding_hnsw_idx` on `chunks.embedding` (`vector_cosine_ops`,
> pgvector defaults `m=16, ef_construction=64`) added to `chunks_ddl()`. Chosen over IVFFlat
> because `ensure_schema()` runs the DDL before data loads. Headline p50/p95 + recall@k
> before/after lands when the full-corpus embed (P4) runs.

- **Symptom:** fine at 3k rows, but embedding the full gold corpus (225k) makes every
  review/doc query scan all vectors. Latency grows linearly with corpus size.
- **Root cause:** `chunks_ddl()` creates a PK, a btree on `source_type`, and a GIN FTS
  index on `text`, but **no index on the `embedding` column** — so pgvector does exact
  (sequential) nearest-neighbour search.
- **Fix:** add an approximate-nearest-neighbour index on `embedding` — **HNSW** (high
  recall, standard) or IVFFlat (lighter, tune `lists`/`probes`). Decide the distance op
  class to match the query (cosine). Measure p50/p95 + recall@k before vs after via the M7
  gate — that before/after is the deliverable.
- **Where:** `backend/retrieval/schema.py` (`chunks_ddl`); verify the query in
  `backend/retrieval/vector_store.py` uses the indexed operator.

## B-6 — Indexer loads the entire corpus into RAM — MEDIUM — ✅ DONE 2026-11-01 (`5b86f3e`)

> **Done.** `index_reviews.py` now streams Gold via `to_pyarrow_dataset().to_batches()`
> and embeds+upserts one batch at a time through `_embed_upsert_batch()` with a single shared
> `CostLedger` (cap stays global). Peak RAM is flat regardless of corpus size, so the P4 embed
> is memory-safe. `read_gold_reviews(limit)` kept as a thin wrapper.

- **Symptom:** embedding all 225k reviews spikes memory; the full-gold read is the heavy
  call that stalled before.
- **Root cause:** `read_gold_reviews()` does `DeltaTable(...).to_pyarrow_table().to_pylist()`
  then slices — it materialises every row (with review text) into a Python list at once.
- **Fix:** stream the read in row-group / fixed-size batches and embed+upsert per batch, so
  peak memory is flat regardless of corpus size. (Pairs naturally with B-5's full-corpus run.)
- **Where:** `backend/retrieval/index_reviews.py` (`read_gold_reviews`, `embed_and_upsert`).

## B-7 — Add OpenRouter as a generation provider behind the seam — HIGH — ✅ DONE 2026-11-01 (`ce4febd`)

> **Done.** `provider_mode` gains `"openrouter"`; `OpenRouterLLM` (in `backend/agents/llm.py`)
> reuses `FreeLLM`'s OpenAI-compatible transport and mirrors `AzureLLM`'s gating
> (`OPENROUTER_GO_AHEAD=true` + `OPENROUTER_API_KEY`). `get_llm(*, model=None)` lets the B-8
> study build a per-slug client without mutating the global settings. `openrouter` ⇒ hosted
> LLM + local free embeddings. Dormant until the go-ahead flag + key are set. Unblocks B-8.

- **Symptom:** generation is limited to local Ollama (small models) or gated Azure; no clean
  way to run open-weight hosted models for the comparison study.
- **Root cause:** the provider seam exposes `free` (local OpenAI-compatible) and `azure`;
  there is no `openrouter` adapter.
- **Fix:** add an `openrouter` provider (OpenAI-compatible base URL + keyed) behind the
  existing seam. Must let the eval harness construct an LLM client per arbitrary model slug
  **without mutating global config**, and respect the cost ledger. Open-weight models only
  (portable to on-prem later); log any spend in `COST.md`. Keep behind a go-ahead flag like
  the Azure path.
- **Where:** provider/LLM factory in `backend/` (where `get_llm()` / the free/azure adapters
  live), `app/config.py`, `.env.example`.

## B-8 — Controlled model-comparison evaluation study — HIGH

- **Symptom:** model choice is currently by assertion, not evidence — not a defensible story
  for recruiters.
- **Root cause:** M7 measures a single configured model; there is no multi-model harness.
- **Fix:** extend M7 into a controlled study over the 6 target models (Mistral + Gemma,
  small/mid/large) via B-7. **Hold embeddings, retrieval, and SQL fixed; vary only the
  generation model.** Metrics: SQL correctness, routing accuracy, grounded-path rate,
  citation validity, latency p50/p95, $/query, plus a license/portability column. Output a
  `docs/` comparison report + the golden set it runs on. Depends on B-7.
- **Where:** `backend/eval/`, golden-set fixtures, `docs/` report.

## B-9 — Embedder bake-off (retrieval-quality axis) — MEDIUM, optional

- **Symptom:** `all-MiniLM-L6-v2` (384-dim) is a fast $0 baseline, not necessarily the best
  retrieval quality.
- **Root cause:** embedder was never compared against stronger open-weight options.
- **Fix:** evaluate MiniLM vs open-weight alternatives (e.g. `bge-base/large`, `e5-base`,
  `nomic-embed-text`) on recall@k / MRR against the golden set. NOTE: changing embedder
  changes the vector **dimension** → recreate `chunks.embedding vector(N)` and **re-embed
  everything**, and the query-time embedder must match the stored one. Keep this a **separate
  experiment from B-8** — vary one axis at a time (embedder here, generation model there).
- **Where:** `backend/retrieval/embeddings.py`, `app/config.py` (`EMBEDDING_MODEL_FREE`),
  `backend/retrieval/schema.py` (dim), `backend/eval/`.

## B-10 — Composer flattens structured SQL into prose; UI re-scrapes it — MEDIUM

- **Symptom:** SQL answers show wrong "metrics" (a year plotted as a value), full float
  precision, mid-value truncation, and no real chart — reads developer-first, not user-first.
- **Root cause:** `composer._sql_text()` flattens SQL rows to a prose string and the
  structured rows/columns are dropped before the API; the frontend then regex-scrapes the
  first number back out of the prose.
- **Fix:** pass the structured SQL result (columns + rows) through `AnswerResult`/the API as
  a typed data block, and render it as a table/chart in the role shapes instead of scraping
  prose. Keep grounding/citation invariants.
- **Where:** `backend/agents/composer.py`, `backend/app/main.py`, `frontend/src/api/types.ts`,
  `frontend/src/answer.ts`, `frontend/src/components/shapes/`.

## B-11 — Production vector query defeats the HNSW index (`, id` tiebreaker) — HIGH (B-5 follow-up)

- **Symptom:** the B-5 HNSW index is built and healthy, but every live `review_rag`/vector
  query still does a **sequential scan** over all 225k vectors — the index is never used, so
  B-5's ~125× speedup is not realized in the serving path.
- **Root cause:** `PgVectorStore.query()` orders by `embedding <=> %s, id` (an `id` tiebreaker
  for deterministic ties). A secondary `ORDER BY` key forces Postgres into a full Sort node,
  which the HNSW index cannot satisfy — so the planner falls back to a `Parallel Seq Scan`.
  pgvector only uses the index when the `ORDER BY` is **distance-only** + `LIMIT k`. Verified
  live via `EXPLAIN`: distance-only ⇒ `Index Scan using chunks_embedding_hnsw_idx`; with `, id`
  ⇒ `Seq Scan`.
- **Fix:** keep both the index *and* deterministic ordering by splitting it — an **inner**
  query does the ANN search (`ORDER BY embedding <=> %s LIMIT k`, hits the index), an **outer**
  query re-sorts those k rows by `score DESC, id`. Re-run the B-5 benchmark against the
  production query form as the acceptance evidence (target: ~0.5 ms p50, was ~61 ms).
  Measured 2026-11-01 (post-recovery, production `query()` form, 100 sampled query vectors):
  `EXPLAIN` confirms the prod form uses `chunks_embedding_hnsw_idx` (Index Scan) while the
  pre-B-11 `, id` form falls to a Seq Scan. brute-force p50 79.0 ms / p95 89.0 ms →
  HNSW p50 2.04 ms / p95 2.88 ms, ≈39× / ≈31×, recall@10 mean 98.5% (min 70%) — ordinary HNSW
  approximate recall at default `ef_search`, with near-duplicate review vectors as equidistant
  ties. Index-usage on the serving path is the decisive acceptance signal and passes.
- **Where:** `backend/retrieval/vector_store.py` (`PgVectorStore.query`); the `keyword_query`
  path is unaffected. Benchmark harness: adapt `scratchpad/bench_b5.py`.

## B-12 — Test fixture drops the real `chunks` table (destroyed the P4 corpus) — HIGH (safety)

- **Symptom:** running `backend/tests/test_vector_store.py` destroyed the live local P4 corpus
  (225k reviews + 79 docs + HNSW index, ~949 MB). Verified 2026-11-01: `rag` DB fell to 8.2 MB,
  `to_regclass('public.chunks')` → `None`. No cloud money and no cloud data involved — local only,
  recoverable by re-running the P4 embed ($0, build-time).
- **Root cause:** the test's `store` fixture runs `DROP TABLE IF EXISTS chunks` for a clean slate,
  but connects via `DATABASE_URL`, which points at the **real local `rag` DB** — not an isolated
  test database. Any run of that file wipes whatever corpus is loaded.
- **Fix:** isolate the test database — point the suite at a dedicated `rag_test` DB (separate
  `TEST_DATABASE_URL` / fixture), **and** add a safety guard so the fixture refuses to `DROP`
  unless the target DB name ends in `_test`. Must land **before** `test_vector_store.py` is run
  again, or a rebuilt corpus will be wiped a second time.
- **Where:** `backend/tests/test_vector_store.py` (the `store` fixture), test config / conftest,
  `.env.example` (document the test DB URL). Sequencing: B-12 fix → P4 recovery → B-11 benchmark.
