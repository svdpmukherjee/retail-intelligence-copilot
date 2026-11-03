# COST.md

Cloud spend log. Every action that spends money is logged here; nothing is
provisioned or run without explicit human go-ahead. Runtime cap lives in
`Settings` (`max_cost_usd`, `max_tokens_per_query`) and is enforced by `CostLedger`.

| Date       | Module | Service                  | Estimated (USD) | Actual (USD) |
|------------|--------|--------------------------|-----------------|--------------|
| 2026-10-27 | M1     | none (IaC stubs only)    | 0.00            | 0.00         |
| 2026-10-27 | M2     | none (Spark local mode)  | 0.00            | 0.00         |
| 2026-10-27 | M3     | none (local embed+pgvec) | 0.00            | 0.00         |
| 2026-10-27 | M4     | none (free LLM/retrieval)| 0.00            | 0.00         |
| 2026-10-27 | M5     | none (determ. summariser)| 0.00            | 0.00         |
| 2026-10-27 | M6     | none (local policy/audit)| 0.00            | 0.00         |
| 2026-10-27 | M7     | none (free eval + CI gate)| 0.00           | 0.00         |
| 2026-10-28 | M8     | none (inert deploy, free) | 0.00            | 0.00         |
| 2026-10-29 | M8v3   | none (inert deploy, free) | 0.00            | 0.00         |
| 2026-10-29 | P1     | Azure Postgres Flexible Server `ric-pg-13396` (GeneralPurpose `Standard_D2ds_v5`, 2 vCore, 32 GB, v16, Sweden Central) — GP fallback after burstable B1ms/B2s hit RegionalAllocationFailed | ~€4–5/day up | (hosting, running) |
| 2026-10-29 | P1     | Blob storage `ricstore28276` + `gold` container (created earlier this phase) | ~€0 (LRS, tiny) | ~0.00 |
| 2026-10-29 | P2     | Connectivity + schema smoke (CREATE EXTENSION vector + 5 schemas, live DB tests) — no new paid service | €0 incremental (rides P1 hosting) | 0.00 |
| 2026-10-29 | P3     | Real medallion ETL in **local Spark** over `data/raw/` (1.5M rows, 15 cats) → Gold Delta published to Blob `gold/` (~93 MB). No Databricks serverless (unimplemented seam) → €0 compute | ~€3–8 (orig. Databricks est.) → **€0 compute** | ~0.00 (Blob storage only, negligible) |
| 2026-11-01 | B-8 | OpenRouter: B-8 model-comparison study run (6 models; answer-path actual) | 0.0266 | 0.0054 |

**P1 hosting now burning** (~€4–5/day). Dominant cost = time the stack is left up — move P1→P8 promptly, then `az group delete -n rg-ric-demo`.

---

## Cloud activation plan (2026-10-29)

One-shot **"prove it live → capture evidence → tear down"** run on the **€175 Azure
free credit (expires 2026-11-25)**. Decision + rationale: see the "Cloud activation"
ADR in `context/DECISIONS.md`. Nothing here has spent yet; each paid step flips its
go-ahead flag only at the start of its phase and is logged in the ledger above the
same day.

### Budget

- **Hard cap: €150** (deliberately below the €175 credit; a ~€25 buffer absorbs
  estimate error and the cost of leaving the stack up a little too long).
- **Azure budget alert: already configured** (`infra/budget.bicep`, carried since M1)
  — consumption budget + alert, armed when real provisioning starts in P1.
- **Kill switch (teardown): `az group delete -n rg-ric-demo`** — deletes the whole
  resource group and stops all burn. This is the end of P8 and the answer to any
  alert or overrun; when in doubt, run it.

### Rough per-phase cost estimates

| Phase | What spends | Driver | Rough estimate |
|-------|-------------|--------|----------------|
| P1 | Provision + hosting (Azure Postgres Flexible Server, Blob, Container Apps / Static Web Apps, Azure OpenAI resource) | **Main ongoing burn** — hosting accrues per hour the stack is up | ~€2–5 / day up; keep the window short |
| P2 | Connectivity + schema smoke (no new paid service) | Rides P1 hosting only | €0 incremental |
| P3 | Databricks **serverless** batch ETL (medallion → Delta → Blob) | Short auto-terminating serverless job | ~€3–8 one-off |
| P4 | Embedding (`text-embedding-3-small`, ~225k chunks, optional 512-dim) | One-time bulk embed, capped by `MAX_EMBEDDING_USD` ($5) | **~€1** one-off |
| P5 | Azure OpenAI chat (live queries) | A handful of demo/eval queries, capped by `MAX_COST_USD` / `MAX_TOKENS_PER_QUERY` | < €1 |
| P6 | Re-run eval gate against Azure | Same chat/embedding paths as P5 | < €1 |
| P7 | Deploy (hosting the app) | Folds into P1 hosting while the stack is up | included in P1 |
| P8 | Evidence capture + **teardown** | Screenshots, then `az group delete` | €0 (stops burn) |

**Dominant cost = time the stack is left running (P1 hosting), not the one-off
embed/ETL.** The €150 cap is comfortable *if the window is kept to days, not weeks*;
the mitigation is to move through P1→P8 promptly and tear down. Expected total for a
tight run: **well under €30**; the cap and alert exist to catch a forgotten-stack
overrun, and the kill switch ends it.

### Phased go-ahead checklist (P1–P8)

Each phase is its own later session. ✅ = human go-ahead required before the flag
flips / the spend starts (cost gate). Flags are the `.env` keys from `.env.example`.

- [x] **P1 — Provision + wire data plane.** ✅ Create `rg-ric-demo` + resources; arm the
      budget alert. Set `DATABASE_URL` → Azure Postgres, `AZURE_BLOB_CONNECTION_STRING` /
      `AZURE_BLOB_CONTAINER` → the storage account. *No provider/LLM/embed flag yet.*
      (`VECTOR_STORE` stays `pgvector`.)
- [x] **P2 — Connectivity + schema smoke.** Point the app at Azure Postgres; create the
      memory/audit schemas; run the suite against the cloud DB. *No new flag, no new
      paid service — rides P1 hosting.* (DONE 2026-10-29: vector ext + 5 schemas created,
      `chunks` at dim 512; 11 live DB tests passed.)
- [x] **P3 — Run the real ETL.** `ETL_STORAGE=blob`, `ETL_RUNTIME=local`. Databricks-serverless
      was never implemented in code (gated seam); ran the real medallion pipeline in **local
      Spark** over `data/raw/` (1.5M→911,308 silver; Gold 911,308 structured / 225,000 reviews,
      15 cats) → Gold Delta published to Blob `gold/`. **€0 ETL compute.** (DONE 2026-10-29.)
- [ ] **P4 — Embed the corpus for real.** ✅ `AZURE_EMBEDDING_GO_AHEAD=true`. One-time bulk
      embed (~225k chunks) into Azure-Postgres pgvector, under the `MAX_EMBEDDING_USD` cap.
- [ ] **P5 — Turn the Azure LLM path on.** ✅ `PROVIDER_MODE=azure`, `AZURE_LLM_GO_AHEAD=true`.
      Run a live grounded + cited query end-to-end against Azure OpenAI.
      (`RERANK_GO_AHEAD` stays `false`.)
- [ ] **P6 — Re-run the eval gate against Azure.** Execute the M7 gate on the live Azure
      paths; record recall@k / MRR / faithfulness / cost / p50–p95 latency.
- [ ] **P7 — Deploy.** ✅ Deploy backend + frontend to the P1 host; capture the live URL.
- [ ] **P8 — Evidence + teardown.** Screenshot the live answer, eval gate, and deployed
      UI under `docs/img/`; log final actuals in the ledger; then **`az group delete -n
      rg-ric-demo`** to stop all burn.

### 2026-11-03 — M7 Stage 1 hosted quality probe

User authorized at most **$2 additional generation spend** using existing provider
credentials. Preflight: public model pricing read, existing database/index read,
cached embeddings only. Hosted execution was rejected by automatic approval review
pending explicit evidence-transfer authorization. **Generation requests: 0;
additional generation spend: $0.** No reindex, downloads or provisioned services.

After explicit user approval of evidence transfer, the bounded M7 probe completed:
**60 OpenRouter requests; provider-reported actual generation cost $0.002433719**
(cost supplied on all 60 requests). Conservative retained reservations $0.07857544;
approved cap $2. Request ceiling reached; no further generation calls. Journal:
`/private/tmp/ric-quality-hosted-stage1.budget.json` (local only, temporary).
No reindex, embedding API calls, downloads, provisioning, deployments or data writes.

### 2026-11-03 — Answer quality Stage 2

Additional generation/cloud API spend **$0**. Six read-only SQL/retrieval smoke
checks used existing Gold/indexes and cached offline embeddings with all model
generation explicitly disabled. No reindex, downloads, provisioning, deployment
or data writes. Stage 1's $0.002433719 actual remains the only new hosted spend.

### 2026-11-03 — User-requested Stage 2 live browser validation

Existing OpenRouter/evidence-transfer approval continued under the remaining $2
budget for the user's explicit live-browser request. Isolated actual Chrome/UI/API
run: **24 hosted calls; provider-reported actual $0.000890035** (24/24 cost coverage),
retained upper reservation $0.02789944. Combined actual with Stage 1 $0.003323754.
No extra hosted calls for mobile replay/evidence checks. Existing corpus read-only,
chat storage ephemeral; no provisioning, reindex, downloads or deployment. Local
journal `/private/tmp/ric-stage2-browser/budget.json`; screenshots/report adjacent.

### 2026-11-03 — Answer quality Stage 3 isolated foundations

Additional hosted/cloud spend **$0**. Read-only existing SQL/Gold/index coverage
audit; real cached local embeddings over synthetic bounded fixture sources, local
SQLite/FTS and Delta artifacts; two-review temporary Spark projection check using
existing Java/cached jars. No model downloads, provider requests, serving corpus
writes, real backfill, deployment or provisioning. Total approved live-test spend
remains **$0.003323754**. Separate authorization is required for real backfill/cutover.

### 2026-11-03 — Practical source/narration/presentation fixes

Additional hosted/cloud spend **$0**. Existing Silver/Gold/index read-only checks,
local cached query embeddings, isolated real Chrome/React/FastAPI runs with all
hosted generation disabled and ephemeral chats. No corpus re-embedding, index/schema
mutation, ETL run, model/package downloads, deployment or provisioning. Earlier
hosted actual remains **$0.003323754**. Temporary test services stopped.

- 2026-11-03 combined-question follow-up: $0 additional provider/cloud spend.
  Focused hermetic checks and generation-disabled read-only local smoke only.
  Prior provider-reported total remains $0.003323754.

- 2026-11-03 conversational correction: $0 additional provider/cloud spend.
  Scripted model tests, offline cached embeddings and read-only existing-data
  smokes; no hosted completions. Runtime understand/compose now use configured
  large tier under the existing per-query budget; hosted quality/cost unmeasured.
  Prior provider-reported total remains $0.003323754.

### 2026-11-03 — Authorized real-user conversation repair/rechecks

- Actual isolated Chrome/React/FastAPI, existing configured OpenRouter models,
  read-only corpus and RAM-only test conversations: 71 turns across27distinct
  queries, including debug failures/replays and targeted rechecks.
- 118 hosted attempts; 114 report cost, 4 HTTP failures have no cost report.
  Provider-reported additional cost **$0.010445375**; cumulative reported with
  earlier$0.003323754 = **$0.013769129**. Missing error-call billing is not assumed0.
- Conservative reservations retained across server restarts: **$0.42382848** under
  the shared$1.50test cap and original$2authorization; no further paid runs planned.
- Local budget journal `/private/tmp/ric-natural-browser/budget.json` (not Git).
  No ETL/reindex/embedding/model downloads, provisioning or deployment costs.

### 2026-11-03 — Documentation audit and Git publication

New provider/cloud/embedding spend **$0**. Existing local Ruff/Black, inspected
DB-free pytest suites and frontend checks only; no new hosted campaign, Spark,
corpus indexing or deployment. Reported remediation total remains $0.013769129.
