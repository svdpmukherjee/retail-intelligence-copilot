# BACKLOG_PLAN.md — delivery blueprint

Produced by the **Product Owner** (`/prioritize`) from `context/BACKLOG.md`. It is the
orchestrator's execution map: what to build next, in what order, and what may run in
parallel. **Severity** (in BACKLOG.md) is impact-if-it-occurs; **Rank** below is the
decision — severity + value + effort + dependencies. Regenerate whenever the backlog
changes; this is derived, not hand-maintained.

_Last ranked: 2026-11-01. Covers B-1…B-10._

## Ranked plan

| Rank | Item | Severity | Value | Effort | Depends on | Wave | Track | File domain | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **B-7** OpenRouter provider | HIGH | High | M | — | 1 | A | LLM factory, `app/config.py`, `.env.example` | TODO |
| 2 | **B-5** HNSW ANN index | HIGH | High | M | — | 1 | B | `retrieval/schema.py`, `retrieval/vector_store.py` | TODO |
| 3 | **B-8** 6-model eval study | HIGH | High | L | B-7 | 1 | A | `eval/`, golden-set fixtures, `docs/` | TODO |
| 4 | **B-6** streaming indexer read | MEDIUM | Med | S | — | 1 | B | `retrieval/index_reviews.py` | TODO |
| 5 | **B-10** composer structured passthrough | MEDIUM | High (visible) | M | — | 2 | C | `agents/composer.py`, `app/main.py`, `frontend/src/{api/types.ts,answer.ts,components/shapes}` | TODO |
| 6 | **B-1** router "why?" tweak | MEDIUM | Med | S | — | 2 | D | `agents/router.py` | TODO |
| 7 | **B-2** free-path history | HIGH | Med (now) | M | B-1, B-10; benefits from B-7 | 3 | C | `agents/router.py`, `agents/composer.py`, memory wiring | TODO |
| 8 | **B-3** support-shape tag | MEDIUM | Med | S | B-10 | 3 | C | `frontend/src/components/` (support shape) | TODO |
| 9 | **B-4** citation mid-word truncation | LOW | Low | S | B-10 | 3 | C | `frontend/src/components/` (citation render) | TODO |
| 10 | **B-9** embedder bake-off | MEDIUM | Med | L | B-5, B-7, B-8 | 4 | — | `retrieval/embeddings.py`, `app/config.py`, `retrieval/schema.py`, `eval/` | TODO |

## Conflict matrix — never run these concurrently

| Shared file | Items |
|---|---|
| `retrieval/schema.py` | B-5, B-9 |
| `agents/composer.py` | B-2, B-10 |
| `agents/router.py` | B-1, B-2 |
| `app/config.py` | B-7, B-9 |
| `eval/` | B-8, B-9 |
| `frontend/src/components/` | B-3, B-4, B-10 |

## Wave plan (parallelism + merge order)

- **Wave 1 (parallel):** Track A `B-7 → B-8` ‖ Track B `B-5 → B-6`. File-disjoint.
  Merge order: Track B (retrieval) then Track A (provider).
- **Wave 2 (parallel):** `B-1` (router) ‖ `B-10` (composer + API + frontend). File-disjoint.
- **Wave 3 (serial):** `B-2` (needs router *and* composer, so after B-1 and B-10) → `B-3` → `B-4` (frontend, after B-10).
- **Wave 4:** `B-9` (solo; touches schema, config, and eval — after B-5, B-7, B-8).

**Runtime caveat:** all tracks share **one local Postgres + one `data/` lake**. Code
edits parallelize safely, but **DB-mutating runs must be serial** — only one track at a
time may build the index (B-5), embed (B-6/B-9), or run eval (B-8). For true runtime
isolation, give a worktree its own DB (`docker compose -p ric2 … 5433:5432`).

## Why the top tier is first
- **B-7** is pure code (no DB) and **unblocks B-8**, the headline model-comparison deliverable.
- **B-5** is the biggest retrieval win and the thing that makes a full-corpus embed worth doing.
