# CURRENT_TASK.md

**No task in progress.** Last session (2026-11-01) closed out the Wave-1/Wave-2 backlog
and a data-loss recovery. `main` = `f12af36`, synced with `origin/main`; working tree clean.

## Done and merged to `main` (see WORKLOG for detail)
- **B-5 / B-6 / B-7** (HNSW index · streaming indexer · OpenRouter provider seam) — Wave 1.
- **data-op P4** — full corpus re-embedded **locally** ($0): 225,000 reviews + 79 docs =
  **225,079 chunks** in local pgvector (`infra-pgvector-1`), dim 384, HNSW index live.
- **B-11** — vector query split (inner distance-only ANN + outer `score DESC, id`) so the
  serving path actually uses `chunks_embedding_hnsw_idx` (≈39× p50 vs seq scan). PR #1.
- **B-12** — `backend/tests/conftest.py` guard: redirects tests to `rag_test`, fails closed
  (fixes the fixture that twice dropped the real corpus). See memory `test-vector-store-drops-real-db`.
- **B-8** — controlled 6-model comparison study (`backend/eval/study.py`, `docs/model-comparison.md`).
  Live run done, $0.0054. Quality is model-independent here; models differ on routing/latency/$/license.
- **B-10** — structured SQL passthrough (`SqlBlock` on `AnswerResult`, real `SqlTable`, no prose-scraping);
  display row cap tied to `sql_agent.MAX_ROWS` + "X of Y" label.

## What's next (pick one; open a NEW session)
- **Remaining backlog items** (all unblocked now that B-8/B-10 merged): **B-2** (HIGH — free-path
  follow-ups ignore conversation history), **B-3** (MEDIUM — SupportShape FIX/ISSUE mislabel),
  **B-4** (LOW — citation snippet truncates mid-word), **B-9** (MEDIUM, optional — embedder bake-off).
  `BACKLOG_PLAN.md` is now stale → run **`/prioritize`** first, then **`/change <ID>`**.
  Note: B-4 and B-2 both touch `composer.py` → serialize (B-4 → B-2); B-9 re-embeds the corpus → run alone.
- **Module M9 — Documentation** (the last remaining *module* in `PROJECT.md`): `/module M9`.

## Parked (not next unless reprioritized)
- **Cloud operationalization P5–P8** (Azure LLM path, Azure eval gate, deploy, teardown) — the
  Azure data plane was parked on 2026-11-01 in favour of the $0 local build; P1–P4 are done.
  Runbook: `data-pipeline-setup/cloud/CLOUD_SETUP.md`. **Azure Postgres `ric-pg-13396` may still
  be burning ~€4–5/day — verify / tear down with `az group delete -n rg-ric-demo` if not needed.**

## Carried open items (from M8 v3, human)
Phone reflow spot-check on a real device; 4 error-state banners not force-driven; per-turn
`audit`/`citations` persistence is a pending schema change for full-fidelity resume; a demo
`support_1` thread left in the dev DB (harmless).

## In progress: M5.5 (B-2 /change under M5) - built, awaiting tester
- `effective_query` + `_is_vague_followup` in `backend/memory/manager.py`; `pipeline.answer` routes/retrieves on
  the augmented query, composes + audits the original; `audit.memory.followup_augmented` added.
- Tests added in `backend/tests/test_pipeline_memory.py` (2 unit + 1 live free-path smoke).
- Left: tester run of the live smoke; then orchestrator close-out.

- 2026-11-01 test-infra: DB fixtures bounded + split (session-scoped read-only `indexed_chunks`, function-scoped memory reset `live_db`); test_pipeline_memory ~40 min -> ~13 s; test_index_reviews/test_pipeline index a 50-row slice. No product code changed.
- 2026-11-02 B-4: word-boundary truncation (_truncate in composer.py, used by _snippet + _extractive) + 4 unit tests in test_composer.py. Left: tester/close-out.
- 2026-11-02 B-3: removed per-line FIX/ISSUE tag from SupportShape.tsx + dead .kv .k/.fix CSS; typecheck/build run. Left: human visual check/close-out.
