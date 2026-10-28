# Spec M2: Data ingestion & ETL

## User story
As the engineering team building the copilot, I want a medallion (Bronze→Silver→Gold)
ETL pipeline that turns Amazon Reviews 2023 into clean, typed, PII-redacted Delta
tables — split into a broad structured layer (SQL) and a narrow free-text layer (RAG) —
so that later indexing (M3) and the SQL/RAG agents (M4) have trustworthy, build-time
data to read, with the pipeline runnable at $0 locally and the Databricks/Blob path
behind the provider seam.

## Module acceptance criteria
- [ ] A PySpark pipeline runs **locally (Spark local mode) at $0** end-to-end over a
      tiny committed sample and produces Bronze, Silver and Gold layers on the local
      filesystem; no cloud resource is provisioned or called to verify.
- [ ] Runtime/storage are chosen via `Settings` (`ETL_RUNTIME=local|databricks`,
      `ETL_STORAGE=local|blob`), following M1's provider-adapter pattern; the
      Databricks/Blob paths exist but are **inert and gated** on explicit go-ahead.
      Every new key is in `backend/.env.example`.
- [ ] Silver enforces the **2019–2023** window and types the structured columns
      (`rating` float, `price` float, `category` str, `verified_purchase` bool,
      `timestamp`/`year`); malformed rows are dropped, not silently coerced.
- [ ] **PII is redacted at ingestion**: reviewer identifiers (`user_id`, reviewer
      name, any free-text email/phone) are hashed or removed before Silver is written;
      no raw reviewer PII exists in Silver/Gold artifacts.
- [ ] Gold emits two tables, both over **15 categories** (broad-on-both): a
      **structured** table (`category`, metrics columns, join keys) for SQL capped at
      `sql_rows_per_category` (100k), and a **review-text** table (`asin`, `title`,
      `text`, `description`) for RAG capped at `rag_rows_per_category` (15k) — fields
      split per PRD §5. Per-category caps are applied **deterministically**.
- [ ] A real end-to-end test runs the full pipeline on the sample and asserts row
      counts, schema, window, and absence of PII; `ruff`/`black` pass on `data/`.

## Sub-modules (ordered, each build → verify → integrate)

### M2.1 ETL scaffold, Spark session & storage/runtime seam
- Goal: a local-first Spark entry point, config seam, and a tiny committed sample so
  every later layer has a place to read from and write to.
- Acceptance criteria:
  - [ ] `Settings` gains ETL keys (`etl_runtime`, `etl_storage`, `data_lake_path`,
        `etl_year_min=2019`, `etl_year_max=2023`, `etl_sample_size`,
        `amazon_dataset_id`, `sql_categories`, `rag_categories`,
        `sql_rows_per_category=100000`, `rag_rows_per_category=15000`); all in
        `.env.example`. `sql_categories` and `rag_categories` both default to the
        same **15 categories** (broad-on-both; see DECISIONS.md "Broad on both
        layers, capped embed").
  - [ ] `get_spark()` returns a configured local-mode `SparkSession` with Delta enabled;
        `resolve_layer_path(layer)` returns a local path (or a Blob URI when
        `etl_storage=blob`, which is not exercised locally).
  - [ ] A tiny JSONL sample (~30–50 rows, Amazon Reviews schema, spanning 2018–2024 so
        the window filter is testable) lives under `data/sample/`.
- Build steps:
  1. Add the ETL fields to `backend/app/config.py` (`sql_categories`/`rag_categories`
     as comma-split lists) and document them in `backend/.env.example`.
  2. Create `data/pyproject.toml` (or extend backend deps): `pyspark`, `delta-spark`;
     configure `ruff`/`black` to match M1.
  3. Write `data/etl/spark_session.py` (`get_spark()` with Delta extensions) and
     `data/etl/storage.py` (`resolve_layer_path(layer)` reading `Settings`; Blob branch
     raises a clear "requires go-ahead" error when unconfigured).
  4. Commit `data/sample/amazon_reviews_sample.jsonl` (synthetic rows, no real PII).
- Files to touch: `backend/app/config.py`, `backend/.env.example`,
  `data/pyproject.toml`, `data/etl/__init__.py`, `data/etl/spark_session.py`,
  `data/etl/storage.py`, `data/sample/amazon_reviews_sample.jsonl`.
- Integration point: consumes M1's `Settings`/`get_settings()` and the `PROVIDER_MODE`
  pattern; writes under `data/` which M1 scaffolded and `.gitignore` already excludes
  for generated layers.

### M2.2 Bronze ingestion
- Goal: land the raw source into a Bronze Delta table, schema-on-read, with provenance.
- Acceptance criteria:
  - [ ] `run_bronze()` reads the local sample (default) into a Bronze Delta/Parquet
        table at `resolve_layer_path("bronze")`, preserving all source fields verbatim.
  - [ ] Bronze rows carry ingestion provenance (`_ingested_at`, `_source`); no filtering
        or typing yet (that is Silver).
  - [ ] Running on the sample yields a Bronze table whose row count equals the sample size.
- Build steps:
  1. Write `data/etl/bronze.py`: `run_bronze(spark, source_path)` → read JSONL →
     add provenance columns → write Delta to the Bronze path (overwrite mode).
  2. Default `source_path` to the committed sample; the HF/Databricks full-source path
     is behind `etl_runtime=databricks` and not read locally.
  3. Add a thin CLI (`python -m data.etl.bronze`) using `get_spark()` + `Settings`.
- Files to touch: `data/etl/bronze.py`.
- Integration point: uses `get_spark()` and `resolve_layer_path()` from M2.1; output is
  the sole input to Silver.

### M2.3 Silver — clean, type, window-filter, PII redaction
- Goal: turn raw Bronze into a clean, typed, PII-free table restricted to 2019–2023.
- Acceptance criteria:
  - [ ] `run_silver()` types structured columns (`rating`, `price`, `category`,
        `verified_purchase`, `timestamp`→`year`), drops malformed/null-key rows, dedups
        on (`asin`,`user_id_hash`,`timestamp`).
  - [ ] Only rows with `etl_year_min ≤ year ≤ etl_year_max` survive.
  - [ ] Reviewer PII is redacted: `user_id`→salted hash, reviewer name dropped, and a
        regex scrub removes email/phone from free text before write. No raw PII in Silver.
- Build steps:
  1. Write `data/etl/silver.py`: `run_silver(spark)` reading Bronze, applying casts,
     the year filter, dedup, and a `redact_pii(df)` helper (hash user id, drop name,
     regex-scrub `title`/`text`).
  2. Keep both structured columns and free-text columns in Silver (split happens in Gold).
  3. Add CLI `python -m data.etl.silver`.
- Files to touch: `data/etl/silver.py`.
- Integration point: reads the Bronze path from M2.2; the redaction helper is the
  single enforcement point for the security rule, reused by no later layer.

### M2.4 Gold — curate SQL table + RAG table + manifest
- Goal: emit the two consumer-ready tables (broad structured for SQL, narrow text for
  RAG) plus a run manifest.
- Acceptance criteria:
  - [ ] `run_gold()` writes a **structured** Gold table (filtered to `sql_categories`,
        structured columns + join keys `asin`/`user_id_hash`/`year`) and a **review-text**
        Gold table (filtered to `rag_categories`, `asin`,`title`,`text`,`description`).
        Both default to the same 15 categories.
  - [ ] Each table is capped **per category**: at most `sql_rows_per_category` (100k)
        structured rows and `rag_rows_per_category` (15k) review-text rows per category,
        applied deterministically (stable ordering, e.g. `timestamp` desc then `asin`),
        so a re-run yields the same rows. The caps are config-driven; on the tiny sample
        they don't bite, so the test exercises the cap with a small override.
  - [ ] A `_manifest.json` records row counts per layer/table, **per-category counts**
        for each Gold table, the two caps (`sql_rows_per_category`/`rag_rows_per_category`),
        window, categories, and run timestamp.
  - [ ] An orchestrator `run_pipeline()` chains Bronze→Silver→Gold in one call.
- Build steps:
  1. Write `data/etl/gold.py`: `run_gold(spark)` producing both tables under the Gold path,
     applying the per-category cap deterministically (window `row_number()` over each
     `category` ordered by a stable key, keep `<= cap`), and writing the manifest.
  2. Write `data/etl/pipeline.py`: `run_pipeline()` calling the three stages in order;
     CLI `python -m data.etl.pipeline`.
  3. Record expected categories and caps from `sql_categories`/`rag_categories` and
     `sql_rows_per_category`/`rag_rows_per_category` settings.
- Files to touch: `data/etl/gold.py`, `data/etl/pipeline.py`.
- Integration point: reads Silver from M2.3; Gold tables are exactly what M3 (indexing)
  and M4 (SQL agent) will read — the module boundary that later modules build onto.

## Test plan
- M2.1: `pytest` unit — `resolve_layer_path` returns local paths for `etl_storage=local`
  and raises for unconfigured `blob`; `get_spark()` returns a working local session;
  `ruff`/`black` clean on `data/`.
- M2.2: run `run_bronze()` on the sample; assert Bronze row count == sample size and
  provenance columns present.
- M2.3: run `run_silver()`; assert all years in [2019,2023], structured columns typed,
  and a scan of Silver contains no raw `user_id`/email/phone (PII assertion).
- M2.4: run `run_gold()`; assert structured table limited to `sql_categories`, review-text
  table limited to `rag_categories` with only text fields, and manifest counts match.
  With a small cap override (e.g. `rag_rows_per_category=2`), assert no category exceeds
  the cap and that the capped selection is deterministic across two runs.
- Module end-to-end smoke (the one real check): `python -m data.etl.pipeline` on the
  committed sample in Spark local mode produces Bronze+Silver+Gold+manifest; a pytest
  asserts the window, the typed schema, zero PII, and the two-table split. Runs in CI
  at $0, no cloud. If PySpark cannot start in the environment, the Tester reports that
  plainly — not a silent PASS.

## Security & cost notes
- **Expected cloud spend for M2 = $0; cap = $0.** The default/CI path is PySpark local
  mode over a tiny committed sample. The Databricks/Blob path is inert behind the
  `etl_runtime`/`etl_storage` seam and runs **only** after explicit human go-ahead —
  CHECKPOINT 1 authorizes committing the local pipeline, **not** any cluster start or
  Blob write. Any future real run is logged in `COST.md`.
- **PII:** reviewer identifiers are redacted at ingestion (M2.3) — `user_id` hashed with
  a salt from `Settings`, reviewer name dropped, email/phone scrubbed from free text.
  Only the redacted sample is committed; no raw PII enters git. Generated Bronze/Silver/
  Gold layers stay gitignored.
- **Secrets:** Databricks/Blob credentials only via `.env` (M1 keys reused); never logged.
- No access-control surface here (role→source policy arrives in M6); Gold carries the
  `category` column that M6's policy will later filter on.

## Out of scope
- Any real Databricks cluster start, Blob write, or full 2019–2023 corpus run (gated,
  go-ahead only).
- Embedding / vector indexing and document (PDF) parsing — that is M3.
- The full run at production volume (15 categories, SQL ≤100k/cat, RAG ≤15k/cat,
  ~225k reviews embedded); M2 proves the pipeline on a tiny sample, and the 15-category
  config + caps carry to the gated real run. Embedding (M3) is not run here.
- SQL agent, retrieval, governance enforcement (M4/M6).
