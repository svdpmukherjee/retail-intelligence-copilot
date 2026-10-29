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
- [ ] **P2 — Connectivity + schema smoke.** Point the app at Azure Postgres; create the
      memory/audit schemas; run the suite against the cloud DB. *No new flag, no new
      paid service — rides P1 hosting.*
- [ ] **P3 — Run the real ETL.** ✅ `ETL_RUNTIME=databricks`, `ETL_STORAGE=blob`. Run the
      medallion pipeline on Databricks serverless → Delta/Gold in Blob (auto-terminate
      after).
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
