# Spec M3: Indexing

## User story
As the engineering team building the copilot, I want the curated review subset and the
authored policy/manual documents embedded into a vector store with clean metadata, so
that M4 retrieval (hybrid search + rerank) has a single, access-filterable index to read
— built at $0 in CI on a tiny slice with a free/local embedder, and the Azure OpenAI +
Azure AI Search paths behind the provider seam, gated on explicit go-ahead.

## Module acceptance criteria
- [ ] An **embedding provider adapter** keyed off M1's `provider_mode`: `free` = a local
      embedder (real, $0), `azure` = Azure OpenAI `text-embedding-3-small` (optionally
      512-dim Matryoshka), **inert/gated** until go-ahead. Both satisfy one `Embedder`
      interface; code runs in both modes. New keys are in `backend/.env.example`.
- [ ] A **vector-store adapter** with a `VECTOR_STORE` seam: `pgvector` (default, local
      Postgres, holds the bulk) and `azure_search` (tiny demo slice only, inert/gated).
      A single unified `chunks` schema carries the metadata M4/M6 need (`source_type`,
      `category`, `asin`, `year`, `doc_id`, section/chunk keys, `text`, `embedding`).
- [ ] The **review subset** (M2 `gold/reviews`) is embedded and upserted into the store;
      runs are **deterministic and idempotent** (re-run = same rows, no duplicates).
- [ ] The **authored docs + a few manual PDFs** are parsed → chunked (with metadata) →
      embedded → indexed into the same `chunks` store, distinguished by `source_type`.
      The authored docs are committed as the evaluation ground-truth corpus.
- [ ] Every embedding run is wrapped in M1's `CostLedger` and cost-gated; the default/CI
      path embeds only a **tiny committed slice at $0** (free/local embedder). No cloud
      spend / real embed run happens without explicit go-ahead (CHECKPOINT 1 + cost gate).
- [ ] A **real, non-mocked** end-to-end smoke (free embedder → local pgvector → similarity
      query) passes; `ruff`/`black` clean on `backend/retrieval/`.

## Sub-modules (ordered, each build → verify → integrate)

### M3.1 Embedding provider adapter
- Goal: one `Embedder` interface with a real local implementation and a gated Azure one.
- Acceptance criteria:
  - [ ] `get_embedder()` returns a `FreeEmbedder` when `provider_mode=free` and an
        `AzureEmbedder` when `azure`; both expose `embed(texts: list[str]) -> list[vector]`
        and a `dim` property.
  - [ ] `FreeEmbedder` (local `sentence-transformers` model from `embedding_model_free`)
        produces real vectors of stable `dim` at $0; `AzureEmbedder` raises a clear
        "requires human go-ahead" error unless Azure keys + go-ahead flag are set.
  - [ ] Azure path honours `text-embedding-3-small` with optional 512-dim via
        `azure_embedding_dim` (Matryoshka); dimension is config-driven, not hard-coded.
- Build steps:
  1. Add Settings keys: `vector_store`, `embedding_model_free`
     (`sentence-transformers/all-MiniLM-L6-v2`), `azure_embedding_dim` (512),
     `embedding_batch_size` (64), `max_embedding_usd` (5.0), `index_slice_size` (tiny
     AI-Search demo slice). Document all in `backend/.env.example`.
  2. Write `backend/retrieval/embeddings.py`: `Embedder` protocol, `FreeEmbedder`,
     `AzureEmbedder` (gated), `get_embedder()` factory keyed off `provider_mode`.
  3. Add `sentence-transformers` to backend deps.
- Files to touch: `backend/app/config.py`, `backend/.env.example`,
  `backend/pyproject.toml`, `backend/retrieval/embeddings.py`,
  `backend/tests/test_embeddings.py`.
- Integration point: reuses M1 `Settings`/`provider_mode` and the `PROVIDER_MODE` seam;
  consumed by M3.3/M3.4 and later by M4 query-embedding.

### M3.2 Vector-store adapter & unified chunk schema
- Goal: a store interface + the `chunks` schema that is the M3→M4 boundary.
- Acceptance criteria:
  - [ ] `backend/retrieval/schema.py` defines a `Chunk` model and the `chunks` DDL:
        `id`, `source_type` (`review|doc`), `text`, `embedding vector(dim)`, `category`,
        `asin`, `year`, `doc_id`, `doc_title`, `section`, `chunk_index`, plus a `source`
        column reserved for M6 access-policy filtering.
  - [ ] `get_vector_store()` returns `PgVectorStore` (default) or `AzureSearchStore`;
        `PgVectorStore.ensure_schema()`/`upsert(chunks)`/`query(vector, k)` work against a
        local Postgres+pgvector at $0; `AzureSearchStore` is inert and raises
        "requires human go-ahead".
  - [ ] `upsert` is idempotent on `id` (deterministic id from source keys).
- Build steps:
  1. Write `backend/retrieval/schema.py` (Chunk model + DDL, dim from active embedder).
  2. Write `backend/retrieval/vector_store.py`: `VectorStore` protocol, `PgVectorStore`
     (psycopg + pgvector, reads `database_url`), `AzureSearchStore` (gated), factory.
  3. Add `pgvector`/`psycopg` deps; add a `docker-compose.yml` (or doc note) for a local
     pgvector Postgres used by CI/tests.
- Files to touch: `backend/retrieval/schema.py`, `backend/retrieval/vector_store.py`,
  `backend/pyproject.toml`, `backend/.env.example`, `infra/docker-compose.yml`,
  `backend/tests/test_vector_store.py`.
- Integration point: consumes M3.1 `dim`; the `chunks` schema is exactly what M4 reads.

### M3.3 Review embedding & indexing
- Goal: embed `gold/reviews` and load it into the store, deterministically.
- Acceptance criteria:
  - [ ] `index_reviews(limit=None)` reads `gold/reviews` (M2 boundary), builds one chunk
        per review (title+text), carries `category`/`asin`/`year` metadata and
        `source_type="review"`, embeds in batches, and upserts.
  - [ ] Wrapped in `CostLedger`; the free embedder records $0. A re-run upserts the same
        ids with no duplicate rows.
  - [ ] Default run embeds only the tiny committed Gold sample (CI, $0); a full run is a
        separate, gated invocation.
- Build steps:
  1. Write `backend/retrieval/chunking.py` (review chunker; deterministic id from
     `asin`+hash of text).
  2. Write `backend/retrieval/index_reviews.py`: read Gold reviews (parquet/Delta path
     via `data_lake_path`), chunk → embed → upsert; CLI `python -m retrieval.index_reviews`.
  3. Estimate + ledger-record token/USD per batch; free path = $0.
- Files to touch: `backend/retrieval/chunking.py`,
  `backend/retrieval/index_reviews.py`, `backend/tests/test_index_reviews.py`.
- Integration point: reads M2 `gold/reviews`; writes via M3.2 store using M3.1 embedder.

### M3.4 Document parsing & indexing
- Goal: author the policy/manual corpus, parse it (incl. PDFs), and index it.
- Acceptance criteria:
  - [ ] ~15–25 authored policy/manual docs (markdown) + 3–5 manual PDFs live under
        `data/docs/`; authored docs are committed as eval ground-truth.
  - [ ] `index_docs()` parses each doc (markdown directly; PDFs via `pypdf`), chunks with
        section metadata (`doc_id`, `doc_title`, `section`, `chunk_index`,
        `source_type="doc"`), embeds, and upserts into the same `chunks` store.
  - [ ] A query can retrieve a doc chunk distinctly from a review chunk via `source_type`.
- Build steps:
  1. Author the policy/manual markdown set under `data/docs/authored/`; add 3–5 small
     manual PDFs under `data/docs/manuals/` (public-domain/synthetic, no PII).
  2. Extend `chunking.py` with a doc chunker (section-aware, bounded chunk size).
  3. Write `backend/retrieval/index_docs.py`: walk `data/docs/`, parse, chunk, embed,
     upsert; CLI `python -m retrieval.index_docs`. Add `pypdf` dep.
- Files to touch: `data/docs/authored/*.md`, `data/docs/manuals/*.pdf`,
  `backend/retrieval/chunking.py`, `backend/retrieval/index_docs.py`,
  `backend/pyproject.toml`, `backend/tests/test_index_docs.py`.
- Integration point: shares M3.1 embedder + M3.2 store; `source_type` distinguishes docs
  from reviews for M4 docs-RAG vs review-RAG routing and M6 access policy.

## Test plan
- M3.1: unit — `get_embedder()` returns `FreeEmbedder` in `free` mode producing vectors of
  stable `dim`; `AzureEmbedder` raises the gated error without go-ahead.
- M3.2: unit — `PgVectorStore.ensure_schema()`+`upsert`+`query` round-trips against local
  pgvector (seed 3 chunks, nearest-neighbour returns the seeded match); `AzureSearchStore`
  raises gated. If Postgres/pgvector is unavailable, the Tester reports plainly (not PASS).
- M3.3: run `index_reviews()` on the committed Gold sample; assert row count, metadata
  columns populated, `source_type="review"`, and idempotency across two runs ($0 via ledger).
- M3.4: run `index_docs()` on a 2–3 doc fixture (1 md + 1 pdf); assert chunks indexed with
  section metadata and `source_type="doc"`.
- Module end-to-end smoke (the one real check): `provider_mode=free`, local pgvector —
  `python -m retrieval.index_reviews` + `python -m retrieval.index_docs` on the tiny
  committed slice, then a similarity query returns both a review chunk and a doc chunk with
  correct `source_type`. Runs in CI at $0, no cloud, no mocked embedder.

## Security & cost notes
- **Expected cloud spend for M3 = $0; cap = $0 in CI.** The default path is the free/local
  embedder over the tiny committed slice into a **local** pgvector Postgres — no cloud call.
- **Real (gated) Azure run, shown at CHECKPOINT 1 as the cost go-ahead:** embedding the full
  ~225k-review bulk with `text-embedding-3-small` (~11M tokens @ ~$0.02/1M) ≈ **$0.20–$1.00
  one-time**; docs negligible. Hard cap via `max_embedding_usd` (default **$5**) enforced by
  `CostLedger`; any real run logged in `COST.md`. CHECKPOINT 1 authorizes only committing the
  local pipeline — **not** any Azure OpenAI embed call or Azure AI Search provisioning.
- **Secrets:** Azure OpenAI / AI Search / `database_url` only via `.env` (M1 keys reused);
  never logged. **PII:** `gold/reviews` is already redacted (M2); authored docs/PDFs carry no
  PII. `chunks.source`/`category` columns are the hooks M6 access policy filters on at retrieval.

## Out of scope
- Any Azure OpenAI embed call, Azure AI Search provisioning, or the full ~225k-review run
  (gated, go-ahead only).
- **Retrieval itself** — hybrid search (vector + BM25), reciprocal-rank fusion, rerank,
  query-time embedding, and the agents/composer are **M4**. M3 only builds the index + its
  read boundary.
- Access-policy enforcement (M6), evaluation gates/recall@k (M7), and richer Docling layout
  parsing (kept to `pypdf`/markdown here for simplicity).
