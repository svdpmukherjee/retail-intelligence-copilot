# CURRENT_TASK.md

No module in progress.

## ▶ ACTIVE NEXT: Cloud operationalization (P1–P8)

Taking the app from the $0 local build to a one-shot live Azure + Databricks run,
then tearing down. **Phase 0 DONE** (activation ADR in `DECISIONS.md` + budget plan +
checklist in `COST.md`). **P1 (provision) DONE 2026-10-29. P2 (connectivity + schema smoke) DONE 2026-10-29. P3 (real ETL, local Spark → Blob) DONE 2026-10-29.** **Next = P4 (embed the corpus for real).**

**P1 result:** Azure Postgres `ric-pg-13396` (GP `Standard_D2ds_v5`, 2 vCore/32 GB/PG16, Sweden
Central — GP fallback after burstable RegionalAllocationFailed). Firewall = single IP
185.6.235.142. `DATABASE_URL` in `backend/.env` now points at it (password percent-encoded;
local URL kept as a commented P8-revert target). `azure.extensions=VECTOR` allowlisted.
Connectivity smoke PASS (psycopg, PG 16.15). **Hosting burning ~€4–5/day — move promptly.**
Admin password lives only in `backend/.env` (and session scratchpad `pg_creds.env`). If the IP
changes, re-pin the firewall rule.

**P2 result:** On the cloud DB — `CREATE EXTENSION vector` (v0.8.7) + all five app schemas created
via the app's own DDL helpers: `chunks`, `threads`, `messages`, `user_memory`, `audit_log`.
**`chunks.embedding` was created at dim 512** (Azure `text-embedding-3-small` target), not free-mode
384 — the indexers only `ensure_schema()` IF NOT EXISTS, so a 384 table would break P4's 512-dim
upsert. Connectivity confirmed live: 11 DB tests passed against Azure Postgres (memory store, audit
log, `GET /threads`); torch-pulling suites skipped per the known hang. Those tests drop tables in
teardown, so schemas were re-created + re-verified afterward (all 5 present, chunks dim 512). €0
incremental. **Hosting still burning ~€4–5/day.**

**P3 result:** "Databricks serverless" was never implemented in code (three `NotImplementedError`
gates: `get_spark`/`run_bronze` on `etl_runtime=databricks`, `resolve_layer_path` on
`etl_storage=blob`; no Databricks SDK/job/notebook; Bronze read only the 15 KB sample). Human chose
**local Spark → Blob**. Minimal build (spec `docs/operationalization/P3_etl_spec.md`): Bronze now
reads `data/raw/*.jsonl` with category-from-filename; Silver tolerates the real feed's missing
`price`; `storage.resolve_layer_path` always computes local + new `publish_gold_to_blob` uploads the
Gold tree to Blob when `ETL_STORAGE=blob`; Gold calls it; `config.py` category defaults fixed
Patio→Video_Games (`.env` already correct). All 17 ETL unit tests pass. Ran real pipeline in local
Spark (`ETL_STORAGE=blob`, `ETL_RUNTIME=local`) in **61.5s**: bronze 1,500,000 → silver 911,308 →
gold_structured 911,308 / gold_reviews 225,000 (15k × 15 cats), window 2019–2023. Blob container
`gold`: 35 objects under `gold/` (structured + reviews Delta + `_manifest.json`, ~93 MB). Local
`data/gold/reviews` verified readable via P4's `read_gold_reviews`. **€0 ETL compute.** Databricks
serverless remains a documented, still-gated stretch.
**Env to re-run (not committed):** JDK via brew `openjdk@17`; `pyspark==3.5.3`, `delta-spark==3.2.0`,
`azure-storage-blob` installed into `backend/.venv`; run from `backend/` with absolute
`DATA_LAKE_PATH` so `backend/.env` (PII salt + blob conn str) loads. **Hosting still ~€4–5/day — P4 next, move promptly.**

- **Step-by-step runbook (source of truth):** `docs/operationalization/RUNBOOK.md`
- **Budget + per-phase cost + checklist:** `COST.md`
- **Decision + rationale:** the "Cloud activation" ADR in `context/DECISIONS.md`
- To run a phase: fresh session → paste that phase's opening line from the runbook.

(The separate remaining *module* is M9 — Documentation — noted at the bottom.)

---


**M8 v3 — Serving & UI (conversation/memory layer) is DONE** (closed 2026-10-29). Design Track
iteration 3: a conversation shell around the shipped v2 chat on the **unchanged pipeline**, fed by
`design/iteration-3/03_handoff.md`. Built in 5 sub-modules, all first-pass, one one-line
tester-caught build-back (M8v3.5). One read-only backend edge — `GET /threads` + `GET /threads/{id}`
+ `MemoryStore.list_threads`/`get_thread` (label derived in-query, no schema DDL change) — plus the
frontend conversation layer: demo identity switcher (owner selector, not auth), owner-scoped history
rail + phone drawer, stacked multi-turn with honest-degrade resume (D-21), one-at-a-time Evidence.
Governance held invariant (scope chips only from `audit.scope`, redacted snippets verbatim, no
hard-coded categories, scope enforced server-side). Module gate PASS incl. live e2e (free mode, $0)
and a live browser visual-QA gate. Spec `.claude/specs/M8v3_serving_ui.md`; note
`docs/modules/M8v3_serving_ui.md`; ADR in `DECISIONS.md`.

**Open items (human):**
- Phone layout **reflow** at true phone width not visually confirmed — the QA environment couldn't
  drive the browser viewport below ~1353px, so the phone media query (≤760px) didn't trigger; the
  phone drawer's *behaviour* (open/close, focus-in, Escape+return, backdrop, ARIA, content) WAS
  verified by driving the real component. Spot-check the reflow on a real phone/emulator.
- 4 error-state banners (`400` / `502` / `no-evidence` / `degraded-SQL`) not force-driven live
  (carried from M8v2).
- **Pending backend schema change (§2 option c):** persist per-turn `audit` + `citations` (e.g. an
  `assistant_meta` JSONB on `messages`) for full-fidelity resume — spec it before building; until
  then restored turns degrade honestly with the muted "historical turn" note.
- Per-persona UI screenshots (support/marketing/executive) under `docs/img/` and linked in the M8v3
  note (optional polish; QA was driven live this session).
- A demo thread for `user_id=support_1` ("What is the return policy?", ~4 turns + memory rows) was
  left in the dev DB by the browser QA — harmless demo data, deletable.

**Remaining module:** M9 (Documentation — consolidated architecture diagrams + design record),
the last TODO in `PROJECT.md`. Open a new session to run `/module M9`.
