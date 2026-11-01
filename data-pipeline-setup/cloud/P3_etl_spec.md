# P3 ETL — minimal-change spec (local Spark → Blob)

**Context.** The runbook framed P3 as "run the medallion ETL on Databricks
serverless." The code does not implement that: `get_spark()` and `run_bronze()`
raise `NotImplementedError` for `ETL_RUNTIME=databricks`, `resolve_layer_path()`
raises for `ETL_STORAGE=blob`, there is no Databricks SDK/job/notebook, and
`run_bronze()` reads only the committed 15 KB sample — nothing reads
`data/raw/*.jsonl`. Decision (human, 2026-10-29): run the **real** medallion ETL
in **local Spark** over the full corpus and **publish Gold to Blob**; keep the
Databricks-serverless runtime as the documented, gated seam (optional later
stretch). €0 ETL compute.

## Scope (what changes)

1. **Bronze — real multi-file corpus + category from filename**
   (`data/etl/bronze.py`). When no explicit `source_path` is given and
   `<data_lake_path>/raw/*.jsonl` exists, read the whole glob (the 15 real
   category files) and set per-row provenance `_source = input_file_name()`.
   Otherwise fall back to the committed sample (preserves every existing test).
   Derive `category` from the file name **only when the column is absent** (the
   real review feed has no `category`; the sample already carries one).
   `ETL_RUNTIME=databricks` still raises — the seam stays gated.

2. **Silver — tolerate absent optional columns** (`data/etl/silver.py`). The
   real review records have no `price`; add it as a null `float` before the
   cast so Silver doesn't crash. Sample (has `price`) is unaffected.

3. **Storage — local compute, Blob publish** (`data/etl/storage.py`).
   `resolve_layer_path()` now always returns the **local** compute path (Spark
   writes the lake locally; no hadoop-azure jars). `ETL_STORAGE=blob` no longer
   raises — instead it means *also publish Gold to Blob*. New
   `publish_gold_to_blob(gold_root, settings)` uploads the whole local Gold tree
   (both Delta tables + `_manifest.json`) to the `AZURE_BLOB_CONTAINER` under a
   `gold/` prefix via `azure-storage-blob`. Fails loud if the connection string
   / container is unset. New `blob_enabled(settings)` helper.

4. **Gold — publish after write** (`data/etl/gold.py`). After writing the local
   Gold tables + manifest, if `blob_enabled(settings)` call
   `publish_gold_to_blob()` (side-effect + stdout line). The returned manifest is
   **unchanged** (keeps the `manifest == returned` invariant the tests assert).

5. **Category mismatch fix** (`backend/app/config.py`). The committed default
   category lists had `Patio_Lawn_and_Garden`, which is **not** in `data/raw/`
   (which has `Video_Games` instead). `.env` already lists the correct 15 (so the
   live run is already right); align the `config.py` defaults too — swap
   `Patio_Lawn_and_Garden` → `Video_Games` in both lists (stays 15, stays
   identical across SQL/RAG, so `test_default_categories_*` still holds).

6. **Dependency** (`data/pyproject.toml`). Add `azure-storage-blob`.

## Why not the alternatives

- **Spark → Blob directly** (abfss/wasbs) needs the hadoop-azure + storage jars
  and account-key config in a local session — fragile, not minimal. Local
  compute + SDK upload is simpler and keeps compute provably local/€0.
- **Databricks serverless** is real dev + cloud spend for the same Gold; parked
  as a documented stretch behind the still-raising `databricks` seam.

## Acceptance criteria

- `data/tests/test_bronze.py`, `test_silver.py`, `test_gold.py`,
  `test_storage.py` all pass (test_storage updated for the new blob semantics).
- Smoke: `run_pipeline()` over `data/raw/*.jsonl` (ETL_RUNTIME=local,
  ETL_STORAGE=blob) produces local Gold `structured` + `reviews` Delta tables and
  `_manifest.json`, **and** uploads that tree to Blob container `gold/` prefix.
- Manifest shows 15 categories (the `data/raw` set), per-layer counts, window
  2019–2023, caps 100000 / 15000. Blob lists the uploaded Gold objects.
- P4 can still read local `data/gold/reviews` (unchanged read path).

## Caps / data notes

- `ETL_SAMPLE_SIZE` is **dead config** (defined, referenced nowhere) — it caps
  nothing; the real caps are `sql_rows_per_category=100000` /
  `rag_rows_per_category=15000`, applied in Gold.
- Real review records lack `price` / `description` / `category` / `name`
  (they carry `images`); `description`/`images` are dropped by Gold's
  `_select_present`, `name` by Silver's `redact_pii`.
