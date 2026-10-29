# Cloud Operationalization Runbook (P1–P8)

**One-shot "prove it live → capture evidence → tear down"** on the €175 Azure free
credit (expires **2026-11-25**). This is the step-by-step companion to the terse
checklist in [`COST.md`](../../COST.md) and the "Cloud activation" ADR in
[`context/DECISIONS.md`](../../context/DECISIONS.md). Written for a newcomer to
Azure and for a fresh Claude session to execute from.

## How to run a phase (every phase)

1. Open a **fresh terminal session** in the repo.
2. Paste the per-phase opening line (given in each phase below). It tells Claude to
   read this runbook + the relevant code, then execute/guide and **stop at the cost
   gate**.
3. Claude runs the steps, logs spend in `COST.md`, appends a line to
   `context/WORKLOG.md`, ticks the box in `COST.md`'s checklist, and tells you when
   to move to the next phase.
4. **Close out every phase (do this before the next one):** confirm `COST.md` has the
   actual spend + the box ticked, `context/WORKLOG.md` has a dated line, and
   `context/CURRENT_TASK.md` reflects the new state — then **commit & push**:
   `git add -A && git commit -m "Pn: <what happened>" && git push`.
   `backend/.env` is gitignored, so secrets never get committed; never force-add it.

**Golden rules** (from the ADR / cost gate):
- ✅ = a paid step: nothing spends until *you* say go and the `.env` flag flips.
- Flip **one** switch per phase — never all at once.
- The kill switch, usable at any time: **`az group delete -n rg-ric-demo`** (deletes
  everything, stops all burn). When an alert fires or you're unsure, run it.
- The dominant cost is **time the stack is left running** (P1 hosting), not the
  one-off ETL/embed. Move P1→P8 promptly.

Prereqs already done: Section A–D setup (OpenAI resource + 2 model deployments,
Databricks workspace + token, dataset in `data/raw/`, `.env` populated), Phase 0
(this plan). `az login` works; region = **Sweden Central**; RG = **rg-ric-demo**.

---

## P1 — Provision + wire the data plane ✅ (first real spend)

**Goal:** create the storage + database the pipeline needs, and point `.env` at them.

**Do (CLI — the reliable path for a newcomer; the bicep stubs in `infra/` are the
"documented IaC" artifact to reconcile afterward, not the thing that has to work
first):**

```bash
# 1. Blob storage + a container for the Gold/Delta output
az storage account create -g rg-ric-demo -n ricstore$RANDOM -l swedencentral --sku Standard_LRS
az storage container create --account-name <storage-name> -n gold

# 2. Postgres Flexible Server (pgvector) — SMALLEST burstable SKU
az postgres flexible-server create -g rg-ric-demo -n ric-pg-$RANDOM -l swedencentral \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 --version 16 \
  --admin-user ricadmin --admin-password '<strong-password>' --public-access <your-ip>

# 3. Allow the pgvector extension, then (in P2) CREATE EXTENSION vector;
az postgres flexible-server parameter set -g rg-ric-demo -s <pg-name> \
  --name azure.extensions --value VECTOR
```

**Collect + put in `.env`:**
```
AZURE_BLOB_CONNECTION_STRING=   # az storage account show-connection-string -g rg-ric-demo -n <storage-name> -o tsv
AZURE_BLOB_CONTAINER=gold
DATABASE_URL=postgresql://ricadmin:<password>@<pg-name>.postgres.database.azure.com:5432/postgres?sslmode=require
```

**Flags this phase:** none (no LLM/embed/provider flag yet). `VECTOR_STORE` stays `pgvector`.
**Verify:** `az resource list -g rg-ric-demo -o table` shows storage + postgres; you can
`psql "$DATABASE_URL"`.
**Cost:** hosting starts now (~€2–5/day). Arm the budget alert (`infra/budget.bicep` /
portal) if not already.
**Open line:** *"Operationalization P1 — see docs/operationalization/RUNBOOK.md. Provision
Blob + Postgres(pgvector) in rg-ric-demo, then set the three .env keys. Stop at the cost gate before creating anything."*

---

## P2 — Connectivity + schema smoke (no new paid service)

**Goal:** the app talks to Azure Postgres; the vector/memory/audit schemas exist.

**Do:**
```bash
# enable the extension on the DB
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
```
Then create the app schemas. The app creates them via its `ensure_*_schema` / `chunks_ddl`
helpers; the next session reads `backend/memory/schema.py`, `backend/governance/audit.py`,
and `backend/retrieval/` to run the right one-time setup (or just start the backend once
against the cloud DB, which triggers schema creation). Run the backend test suite against
the cloud DB to confirm connectivity.

**Flags:** none. **Cost:** €0 incremental (rides P1 hosting).
**Verify:** `\dt` in psql shows `chunks`, `threads`, `messages`, `user_memory`, `audit_log`.
**Open line:** *"Operationalization P2 — RUNBOOK. Point the app at Azure Postgres, create the
pgvector extension + all schemas, run the suite against the cloud DB."*

---

## P3 — Run the real ETL on Databricks serverless ✅

**Goal:** medallion pipeline over `data/raw/` (15 categories) → Gold Delta in Blob.

**Entrypoint:** `data/etl/pipeline.py` (bronze→silver→gold; `bronze.py`/`silver.py`/
`gold.py`). The next session **reads `data/etl/pipeline.py`** for the exact run command +
args and how the `databricks` runtime branch submits to serverless.

**Do:**
1. Flip `.env`: `ETL_RUNTIME=databricks`, `ETL_STORAGE=blob`.
2. **Check `ETL_SAMPLE_SIZE`** — it was `50` for the committed synthetic sample. Confirm in
   `pipeline.py` it does NOT cap the real run; the real caps are `SQL_ROWS_PER_CATEGORY`
   (100k) / `RAG_ROWS_PER_CATEGORY` (15k). Raise/clear it if it would limit ingestion.
3. Upload `data/raw/*.jsonl` to Blob (or DBFS) where the Databricks job reads them.
4. Run the pipeline on the serverless workspace; let it auto-terminate.
5. Verify `_manifest.json` in Gold (per-layer counts, window, categories).

**Flags:** `ETL_RUNTIME`, `ETL_STORAGE`. **Cost:** ~€3–8 one-off (serverless DBUs; auto-stops).
**Verify:** Gold `structured` + `reviews` Delta tables exist in Blob; manifest counts look right.
**Open line:** *"Operationalization P3 — RUNBOOK. Read data/etl/pipeline.py, confirm ETL_SAMPLE_SIZE
won't cap the real run, upload data/raw to Blob, run the medallion ETL on Databricks serverless, verify the manifest. Stop at the cost gate first."*

---

## P4 — Embed the corpus for real ✅

**Goal:** embed Gold reviews + docs into Azure-Postgres pgvector.

**Entrypoints:** `backend/retrieval/index_reviews.py` (`index_reviews(limit)`, `main()`) and
`backend/retrieval/index_docs.py` (`index_docs()`, `main()`). Read both for exact args.

**Do:**
1. Flip `.env`: `AZURE_EMBEDDING_GO_AHEAD=true` (keep `VECTOR_STORE=pgvector`,
   `AZURE_EMBEDDING_DIM=512`, `MAX_EMBEDDING_USD=5.0`).
2. Run the review indexer, then the doc indexer, reading from the Gold tables P3 wrote.
3. Watch the `CostLedger` — it caps at `MAX_EMBEDDING_USD`.

**Flags:** `AZURE_EMBEDDING_GO_AHEAD`. **Cost:** **~€1** one-off.
**Verify:** `SELECT count(*) FROM chunks;` ≈ up to ~225k (reviews) + doc chunks; log actual $ in `COST.md`.
**Open line:** *"Operationalization P4 — RUNBOOK. Flip AZURE_EMBEDDING_GO_AHEAD, run index_reviews then index_docs into Azure pgvector, verify chunk counts, log the actual embedding cost. Stop at the cost gate first."*

---

## P5 — Turn the Azure LLM path on ✅

**Goal:** serving runs live against Azure OpenAI; a real grounded+cited answer.

**Do:**
1. Flip `.env`: `PROVIDER_MODE=azure`, `AZURE_LLM_GO_AHEAD=true` (keep `RERANK_GO_AHEAD=false`).
2. Start the backend (`uvicorn app.main:app`) + frontend (`npm run dev`).
3. Smoke one query per intent: a policy question (`docs_rag`), a review question
   (`review_rag`), an aggregate (`sql`), a why-changed (`sql_rag`). Confirm each is grounded,
   cited, scoped, and that `cost_usd`/`latency_ms` are populated.

**Flags:** `PROVIDER_MODE`, `AZURE_LLM_GO_AHEAD`. **Cost:** < €1 (a handful of queries, capped by `MAX_COST_USD`/`MAX_TOKENS_PER_QUERY`).
**Verify:** answers now come from the real corpus; `audit.cost_usd` > 0; `/threads` + memory work.
**Open line:** *"Operationalization P5 — RUNBOOK. Flip PROVIDER_MODE=azure + AZURE_LLM_GO_AHEAD, run the stack, smoke one query per intent live, confirm grounded+cited+scoped and cost logged. Stop at the cost gate first."*

---

## P6 — Re-run the eval gate against Azure

**Goal:** measure quality on the real, live paths.

**Entrypoint:** `backend/eval/run_eval.py` (thresholds in `backend/eval/thresholds.json`).

**Do:** run the eval. **Expect to re-tune thresholds** — Azure latency and faithfulness
differ from the local slice; the harness warms up before timing. Capture the metrics table.

**Flags:** none new (uses P5 paths). **Cost:** < €1.
**Verify:** recall@k / MRR / faithfulness / cost / p50–p95 recorded; note any threshold changes in `DECISIONS.md`.
**Open line:** *"Operationalization P6 — RUNBOOK. Run backend/eval/run_eval.py against the live Azure paths, re-tune thresholds if needed, capture the metrics for the portfolio."*

---

## P7 — Deploy ✅

**Goal:** a live URL (the "operationalized" artifact).

**Two options — pick by remaining credit/time:**
- **A (full story):** deploy backend → **Azure Container Apps** (scales to zero), frontend →
  **Azure Static Web Apps**; set `CORS_ALLOW_ORIGINS` to the SWA URL and the frontend's
  `VITE_API_BASE_URL` to the backend URL. The next session reads `backend/Dockerfile`,
  `frontend/Dockerfile`, `infra/webapp.bicep` (the stub to fill) for the exact steps.
- **B (cheaper, if credit/time tight):** skip hosting; run the stack **locally against the
  cloud DB + Azure OpenAI** and record a screen-capture demo. You still prove the real
  cloud pipeline; you just don't expose a public URL.

**Flags:** none new. **Cost:** Container Apps scales to zero (cheap); folds into P1 hosting.
**Open line:** *"Operationalization P7 — RUNBOOK. Deploy backend to Container Apps + frontend to Static Web Apps (option A), wiring CORS + VITE_API_BASE_URL. Stop at the cost gate first."* (or "do option B — run locally against cloud and record a demo.")

---

## P8 — Evidence + teardown

**Goal:** capture proof, then stop all burn.

**Do:**
1. Screenshot under `docs/img/`: a live grounded+cited answer per persona
   (support/marketing/executive), the eval gate output, the deployed UI (if P7-A).
2. Log final actuals in the `COST.md` ledger; add a short "operationalized" note in
   `docs/` and a `WORKLOG.md` line.
3. **Teardown — the point of the whole plan:**
   ```bash
   az group delete -n rg-ric-demo --yes --no-wait
   ```
   This removes storage, Postgres, OpenAI, Databricks (+ its managed RG), and any P7
   hosting — all burn stops. The IaC, screenshots, and $0 local mode remain as the
   permanent demo.
4. **Revert `.env`** to the safe local defaults (`PROVIDER_MODE=free`, `ETL_RUNTIME=local`,
   `ETL_STORAGE=local`, all `*_GO_AHEAD=false`, local `DATABASE_URL`) so the repo runs at $0 again.
5. **Rotate the Databricks token** (it was shared during setup).

**Cost:** €0 (stops burn).
**Open line:** *"Operationalization P8 — RUNBOOK. Capture evidence screenshots + final COST.md actuals, then tear down with az group delete, revert .env to $0 local defaults, rotate the Databricks token."*

---

## Status tracker

Tick here as you go (mirror of `COST.md`):

- [x] P1 provision + wire   - [x] P2 schema smoke   - [ ] P3 real ETL   - [ ] P4 embed
- [ ] P5 LLM live   - [ ] P6 eval   - [ ] P7 deploy   - [ ] P8 evidence + teardown
