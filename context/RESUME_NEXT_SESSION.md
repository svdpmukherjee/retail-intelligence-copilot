# RESUME — next session (written 2026-11-01, end of day)

Branch: `backlog/b11-hnsw-query` (single working tree, the main repo dir). Local only, $0, no cloud.

## What happened today (incident)
- A test fixture (`DROP TABLE chunks`) ran against the **real `rag` DB** and destroyed the
  P4 corpus. Root cause: 10 test suites read the DB URL via `Settings()` (from `.env`) and
  drop/recreate tables, but nothing pointed them at a throwaway DB.
- First recovery succeeded (225,079 chunks). Then a **broken B-12 guard** wiped it AGAIN: the
  first `conftest.py` read `os.environ["DATABASE_URL"]`, but the URL lives in the **`.env` file**,
  not the shell env — so it found nothing and **failed OPEN** (let tests hit real `rag`).

## Current state
- **Corpus: GONE** (`rag.chunks` table does not exist). Recoverable at $0 via re-embed (~13 min).
- **B-12 guard: FIXED + VERIFIED** in `backend/tests/conftest.py` — now reads via `Settings()`,
  redirects the session to `rag_test`, and **fails CLOSED** (aborts if it can't confirm a `_test`
  target). Verified by reproducing the real pytest path (no tests run, nothing dropped).
  **It is now SAFE to run pytest.**
- **B-11 code: DONE + unit-tested, UNCOMMITTED** in the working tree
  (`backend/retrieval/vector_store.py` = distance-only ANN subquery + outer `score DESC, id`).
  Only its acceptance **benchmark** remains (needs the corpus back).
- Uncommitted changes mix **B-11** and **B-12** — split into two commits (see step 5).

## Tomorrow's tasks, in order
1. **Start Docker**, confirm pgvector is up and `chunks` is empty/missing:
   `docker ps | grep pgvector` → then `docker exec infra-pgvector-1 psql -U rag -d rag -c "SELECT to_regclass('public.chunks');"`
2. **Recover the corpus** (from `backend/`, local $0):
   `./.venv/bin/python -m retrieval.index_reviews` then `./.venv/bin/python -m retrieval.index_docs`
3. **Verify**: `docker exec infra-pgvector-1 psql -U rag -d rag -c "SELECT source_type, count(*) FROM chunks GROUP BY 1;"` → expect review 225000 + doc 79 = 225,079, and index `chunks_embedding_hnsw_idx` present.
4. **B-11 acceptance benchmark** against the *production* `PgVectorStore.query()` path (now fixed):
   confirm it uses the HNSW index (~0.5 ms p50 vs ~61 ms brute-force), recall@10 ~100%.
   Record the numbers in B-11 / WORKLOG.
5. **Commit (only when you ask):** split into (a) B-12 = `conftest.py` + `.env.example` +
   BACKLOG B-12 entry; (b) B-11 = `vector_store.py` + `test_vector_store.py` + spec/ADR +
   BACKLOG B-11 entry. Then merge B-11 (and B-12) to main and push.

## Safety note
- Tests are safe now, but the recovered corpus and the tests share one Postgres server
  (`rag` real, `rag_test` throwaway). Run **step 1 before any test** so you know the state.
