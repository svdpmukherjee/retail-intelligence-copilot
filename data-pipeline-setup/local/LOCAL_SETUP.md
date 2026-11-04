# Local data operationalization — set up and run from a clean clone

A fresh `git clone` ships **code + a 40-row sample + the authored docs only** — the real corpus,
the medallion lake (`data/bronze|silver|gold`), the `.env`, and the Postgres vector store are all
gitignored. The module loop (`/module`) builds and verifies code against the committed sample, at
$0. **This runbook is the separate, one-off step that populates the real data on your own machine**
(download the slice → build the lake → embed into pgvector), the local mirror of the cloud
operationalization phase. Run it once after cloning to get a working system with real retrieval.

Works on a fresh macOS / Linux / Windows machine. Commands are grouped; run them top to bottom.
Shell syntax is bash/zsh; Windows PowerShell differences are flagged inline as **(Win)**.
Replace `<REPO>` with the absolute path to this repo on your machine.

---

## A. Prerequisites — install any that are missing

| Tool | Check | Install if missing |
|---|---|---|
| Docker (Desktop/Engine) | `docker --version` | macOS/Win: Docker Desktop installer · Linux: `sudo apt install docker.io` |
| Python 3.12+ | `python3 --version` | macOS: `brew install python@3.12` · Linux: `sudo apt install python3.12 python3.12-venv` · Win: python.org installer |
| Java JDK 17 | `java -version` | macOS: `brew install openjdk@17` · Linux: `sudo apt install openjdk-17-jdk` · Win: `winget install Microsoft.OpenJDK.17` |
| Node 18+ (frontend only) | `node --version` | macOS: `brew install node` · Linux: `sudo apt install nodejs npm` · Win: `winget install OpenJS.NodeJS` |

**Point `JAVA_HOME` at the JDK** (Spark needs it; a missing/placeholder Java gives
`Unable to locate a Java Runtime` / `JAVA_GATEWAY_EXITED`). Set it for your session, or add to
your shell profile:
- macOS: `export JAVA_HOME=$(/usr/libexec/java_home -v 17)`
- Linux: `export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))`
- **(Win)** PowerShell: `$env:JAVA_HOME = (Get-Command java).Source | Split-Path | Split-Path`

Verify: `java -version` prints `17.x`.

---

## B. One-time project setup

```bash
cd <REPO>

# 1. Create + activate a virtual environment
python3 -m venv backend/.venv
source backend/.venv/bin/activate          # (Win) backend\.venv\Scripts\Activate.ps1

# 2. Install app deps (core) + ETL deps (Spark/Delta) into that venv
pip install -e ./backend                   # FastAPI, retrieval, embeddings, DuckDB, pgvector client
pip install "pyspark>=3.5,<4" "delta-spark>=3.2,<4"   # medallion pipeline (Spark local mode)

# 3. Create the secrets file from the template, then edit it
cp backend/.env.example backend/.env       # (Win) copy backend\.env.example backend\.env
#   Edit backend/.env and set two required values:
#     PII_HASH_SALT=<any long random string>   (Silver aborts without it)
#     DATABASE_URL=postgresql://rag:rag@localhost:5432/rag   (matches the Postgres
#        container started in Step C.1; the template ships a <user>:<password>/<db>
#        placeholder that will NOT connect until you set this.)
#   The lake stays local and $0 by default (PROVIDER_MODE=free, local embedder,
#   local Delta lake). Indexing (C.3) and the SQL answer path need nothing more.
#   The CHAT answer path additionally needs an LLM — see "LLM for the chat" below.
#   backend/.env is gitignored — real secrets never leave your machine.

# 4. Install frontend deps
cd frontend && npm install && cd ..
```

### B.5 — Download the raw dataset into `data/raw/`

The pipeline reads `data/raw/<Category>.jsonl` (Bronze derives the category from the file name).
Source = Hugging Face [`McAuley-Lab/Amazon-Reviews-2023`](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023),
path `raw/review_categories/<Category>.jsonl`. The full per-category files are **huge** (10–30 GB
each), so pull only a bounded prefix — the files are plain JSONL, so `curl | head` downloads just
the first N lines and stops. N=200000 per category is plenty; Silver's 2019–2023 window and Gold's
per-category caps bound the final output regardless.

```bash
cd <REPO> && mkdir -p data/raw && cd data/raw
BASE="https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/review_categories"
for C in Electronics Home_and_Kitchen Books Beauty_and_Personal_Care Sports_and_Outdoors \
         Toys_and_Games Automotive Pet_Supplies Cell_Phones_and_Accessories \
         Clothing_Shoes_and_Jewelry Health_and_Household Office_Products \
         Tools_and_Home_Improvement Grocery_and_Gourmet_Food Video_Games; do
  echo "downloading $C ..."
  curl -sL "$BASE/$C.jsonl" | head -n 200000 > "$C.jsonl"
done
```
- The 15 names must match `SQL_CATEGORIES` / `RAG_CATEGORIES` in `backend/.env`.
- Reviews aren't strictly date-sorted; if a category comes out sparse after the 2019–2023 filter,
  raise N and re-download that one.
- **(Win)** run this loop in Git Bash or WSL (it uses `curl`+`head`).

### B.6 — Download the item metadata into `data/raw_meta/` (price, product name, avg rating)

The review feed above carries **no product attributes** — `price`, product name, and the
product's average rating live only in Amazon's separate item-metadata feed
(`meta_<Category>.jsonl`, 10-30 GB each). Those feed Gold `structured`'s `price`,
`product_title`, `product_avg_rating`, `product_rating_count`, and `store` columns; without
this step `price` is null and product-level text-to-SQL questions can't be answered.

The `head` trick does **not** work here (a product's metadata can sit anywhere in the file),
so the helper streams each metadata file once and keeps only the products that appear in the
reviews you downloaded in B.5 — the on-disk result is a few hundred MB, not ~76 GB. Expect
~45 min on a typical connection; run it **from `backend/`** (same env/PYTHONPATH reason as
Step 2).

```bash
cd <REPO>/backend
source .venv/bin/activate
PYTHONPATH=.. DATA_LAKE_PATH=../data python -m data.etl.fetch_product_meta   # -> ../data/raw_meta/
```
- Run B.5 first — this reads `data/raw/<Category>.jsonl` to know which products to keep.
- Amazon's metadata is missing `price` for a large share of products; those rows keep a null
  price (no values are invented). The script prints per-category price coverage.

### B.7 — LLM for the chat answer path (pick one)

The local embedder (`all-MiniLM-L6-v2`) runs on your machine at $0, so **indexing (C.3) and
the SQL answer path work with no LLM key**. Generating a written chat answer needs a language
model. Two options — set the values in `backend/.env`:

- **Easiest (one hosted key).** `PROVIDER_MODE=openrouter`, `OPENROUTER_API_KEY=<your key>`,
  `OPENROUTER_GO_AHEAD=true`. Uses hosted open-weight models (Gemma by default); embeddings
  still stay local. A few $ of credit covers a demo.
- **Fully local (no key, needs Ollama).** Install [Ollama](https://ollama.com), then
  `ollama pull llama3.1` (or any chat model). Keep `PROVIDER_MODE=free` and set
  `FREE_LLM_BASE_URL=http://localhost:11434/v1`, `FREE_LLM_API_KEY=ollama` (any non-empty
  string), `FREE_LLM_MODEL=llama3.1`. Everything stays on your machine at $0.

### B.8 — Observability with Langfuse (optional)

The app runs fully without it; this only lights up the **observability plane** (span-level
pipeline timings, tokens and cost traces). Tracing is **off by default** and activates only
when `OBSERVABILITY_ENABLED=true` *and* both keys are present in `backend/.env`:

```
OBSERVABILITY_ENABLED=true
LANGFUSE_HOST=http://localhost:3000      # or https://cloud.langfuse.com (optional; SDK defaults to cloud)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

- **Hosted:** create a free project at [Langfuse Cloud](https://cloud.langfuse.com) and copy its
  keys.
- **Self-hosted:** run Langfuse's own Docker stack (see the
  [Langfuse self-host guide](https://langfuse.com/self-hosting/local)) — it is a **separate**
  `docker compose` from this repo's `infra/`, listening on `:3000` — then create a project and
  copy its keys.

Traces are redacted (no PII, restricted metadata). Ingestion is async, so a trace appears a few
seconds after the query. Leave the keys unset to run without the observability plane.

---

## C. Run — every time (in order)

### Step 1 — Start Postgres (serving store for vectors + memory + audit)
```bash
cd <REPO>
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps        # wait for STATUS = healthy
```

### Step 2 — Build the lake: raw → bronze → silver → gold (local Spark, ~1 min)
**Run from `backend/`.** Two reasons it must be there: `.env` loads relative to your current
directory (it lives in `backend/`, and Silver aborts without `PII_HASH_SALT`), and the repo root
must be on `PYTHONPATH` so the `data` package imports.
```bash
cd <REPO>/backend
source .venv/bin/activate                            # if not already active
PYTHONPATH=.. DATA_LAKE_PATH=../data python -m data.etl.pipeline
```
**(Win)** PowerShell:
```powershell
cd <REPO>\backend
$env:PYTHONPATH=".."; $env:DATA_LAKE_PATH="..\data"; python -m data.etl.pipeline
```
Writes `data/bronze`, `data/silver`, `data/gold/structured`, `data/gold/reviews`, `_manifest.json`.

Verify:
```bash
# Row counts + columns for the small layers (authoritative via Delta; a part-*.parquet glob
# over-counts because it also sees tombstoned files left by overwrite runs).
cd <REPO>/backend
python - <<'PY'
from deltalake import DeltaTable
for layer in ['bronze', 'silver', 'gold/structured']:
    t = DeltaTable(f'../data/{layer}').to_pyarrow_table()
    print(layer, '->', f'{t.num_rows:,} rows,', len(t.column_names), 'cols:', t.column_names)
PY
```
```bash
# Heavy table (gold/reviews) or any group-by: DuckDB on the Parquet is fast + lazy
# (doesn't pull the review text into RAM).
cd <REPO>/backend
python - <<'PY'
import duckdb
c = duckdb.connect(':memory:')
R = "read_parquet('../data/gold/reviews/part-*.parquet')"   # swap for any layer below
print(c.execute(f"SELECT count(*) FROM {R}").fetchone())
print(c.execute(f"SELECT category, count(*) FROM {R} GROUP BY 1 ORDER BY 1").fetchall())
PY
# swap R to: '../data/gold/structured/part-*.parquet' | '../data/silver/part-*.parquet' | '../data/bronze/part-*.parquet'
```
```bash
# Raw is plain JSONL — inspect with the shell:
cd <REPO>
wc -l data/raw/*.jsonl                  # rows per category file
head -1 data/raw/Electronics.jsonl      # one record's shape/columns
```

### Step 3 — Embed the corpus into Postgres (fills the vector store)
```bash
cd <REPO>/backend
python -m retrieval.index_reviews        # all gold reviews → chunks (add --limit N for a smaller slice)
python -m retrieval.index_docs           # policy/manual docs → chunks
```
Only this step writes to Postgres. Re-running upserts by id (no duplicates). The SQL path needs
none of this — it reads gold Parquet directly via in-memory DuckDB.

Verify:
```bash
# how many, by type
docker exec infra-pgvector-1 psql -U rag -d rag -c "SELECT source_type, count(*) FROM chunks GROUP BY source_type;"

# peek at actual rows + vectors
docker exec infra-pgvector-1 psql -U rag -d rag -c "SELECT source_type, left(text,45), vector_dims(embedding), left(embedding::text,55) FROM chunks LIMIT 3;"

# table size on disk
docker exec infra-pgvector-1 psql -U rag -d rag -tc "SELECT pg_size_pretty(pg_total_relation_size('chunks'));"
```

### Step 4 — Start the backend API
```bash
cd <REPO>/backend
uvicorn app.main:app --reload --port 8000
```
`--reload` watches `.py` only — after editing `.env`, stop (Ctrl-C) and relaunch.

### Step 5 — Start the frontend (separate terminal)
```bash
cd <REPO>/frontend
npm run dev                              # http://localhost:5173
```

---

## D. Reset / housekeeping

```bash
# Stop Postgres but KEEP embeddings (volume survives)
docker compose -f infra/docker-compose.yml down

# Stop Postgres and WIPE embeddings (deletes the volume; must re-run Step 3 after)
docker compose -f infra/docker-compose.yml down -v

# Rebuild the lake from clean (optional; avoids accumulating tombstoned Delta files)
rm -rf data/bronze data/silver data/gold          # never delete data/raw (the source)

# Sweep tombstoned Delta files left by overwrite runs
cd <REPO>/backend && python -c "
from deltalake import DeltaTable
for layer in ['bronze','silver','gold/structured','gold/reviews']:
    DeltaTable(f'../data/{layer}').vacuum(retention_hours=0, enforce_retention_duration=False, dry_run=False)
print('vacuumed')"
```

---

## Query flow (what each store serves)
```
:5173 → POST /query (:8000)
  → router (sql | review_rag | docs_rag | sql_rag)
  → governance: access policy scopes categories BEFORE retrieval
  ├─ sql        → in-memory DuckDB over data/gold/structured  (Parquet on DISK)
  ├─ review_rag → pgvector search on chunks(source_type='review')  (POSTGRES)
  ├─ docs_rag   → pgvector search on chunks(source_type='doc')     (POSTGRES)
  └─ sql_rag    → DuckDB numbers + pgvector evidence
  → composer grounds answer + citations, redacts PII
  → audit_log row (POSTGRES)
```
