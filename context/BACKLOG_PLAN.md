# BACKLOG_PLAN.md — delivery blueprint (Product Owner)

Regenerated 2026-11-01 04:3x (full re-rank, no human focus). Source: `context/BACKLOG.md`
(edited 04:26 — B-1 dropped, B-5/B-6/B-7 DONE+merged, B-4 re-pointed, **B-11 added**).
Advice to the orchestrator — each item still runs as its own `/change`; the human approves
each. Severity = impact-if-it-occurs (from BACKLOG); **priority** = severity + business value
+ effort + risk + dependencies, so the rank deliberately diverges from severity.

Current reality (WORKLOG / git / DECISIONS): M1–M8 + v2/v3 DONE. **Local-only** stack (Azure/Blob
plane parked). **Wave-1 of the old plan shipped: B-5 (HNSW index), B-6 (streaming indexer), B-7
(OpenRouter provider) all DONE+merged 2026-11-01. Data-op P4 — the real 225k full-corpus local
embed — is DONE (`ea02ce5`).** So the index exists AND the corpus is embedded. The fresh find is
**B-11**: the shipped HNSW index is never actually hit by the live serving query, so B-5's ~125×
speedup is currently *unrealized*. Open items now: B-2, B-3, B-4, B-8, B-9, B-10, **B-11**.

## Ranked table

| Rank | Item | Severity | Value | Effort | Risk | Depends on | Wave | Track | File domain | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | B-11 serving query defeats HNSW (`, id` tiebreaker) | HIGH | HIGH | S | L | B-5 (done) | 1 | A | `backend/retrieval/vector_store.py` (`PgVectorStore.query`) | **Ready — top** |
| 2 | B-8 controlled model-comparison study | HIGH | HIGH | L | MED | B-7 (done) | 1 | B | `backend/eval/`, golden-set fixtures, `docs/` report | **Ready (unblocked)** |
| 3 | B-10 structured SQL result passthrough | MED | MED-HIGH | M | L-M | — | 1 | C | `backend/agents/composer.py`, `app/main.py`, `frontend/src/api/types.ts`, `answer.ts`, `components/shapes/` | Ready |
| 4 | B-2 follow-ups ignore history on free path | HIGH | MED | M | MED | B-7 (enabler, done) | 2 | A | `backend/agents/router.py`, `composer.py`, memory `context` wiring | Flagged (design decision) |
| 5 | B-3 support per-line FIX/ISSUE mislabel | MED | MED | S | L | after B-10 (shared shapes) | 2 | B | `frontend/src/components/shapes/SupportShape.tsx` | Ready |
| 6 | B-4 citation snippet truncates mid-word | LOW | LOW-MED | S | L | — (composer) | 2 | A | `backend/agents/composer.py` (`_snippet`) | Ready (re-pointed) |
| 7 | B-9 embedder bake-off (optional) | MED | MED | L | MED | after B-8 (one axis at a time) | 3 | A | `backend/retrieval/embeddings.py`, `app/config.py`, `schema.py` (dim), `backend/eval/` | Deferred/optional |
| — | B-1 vague "why?" false-routes to sql_rag | MED | — | — | — | — | — | — | `backend/agents/router.py` | **DROPPED (resolved) — closed in BACKLOG** |

## Newly reconciled since the 03:12 plan

- **B-5 / B-6 / B-7 → DONE+merged** (`095338c`/`5b86f3e`/`ce4febd`). Old Wave 1 is closed.
- **Data-op P4 (225k local embed) → DONE** (`ea02ce5`). The corpus is embedded; the big
  DB-mutating run is already behind us, so the runtime caveat now applies only to B-9's re-embed.
- **B-1 → DROPPED in BACKLOG** (root cause gone: the `sql_rag` rule already requires `\bwhy\b`
  paired with a change-word). Any residual "bare why? gives a useless answer" is **B-2**.
- **B-4 → re-pointed** to backend `composer._snippet()` (snippets moved server-side in M8 v2);
  BACKLOG already reflects this. Fix the word-boundary truncate there, not in `EvidencePanel.tsx`.
- **B-11 → NEW, ranked #1.** Verified live at `vector_store.py:106`:
  `ORDER BY embedding <=> %s, id LIMIT %s`. The `, id` tiebreaker forces a full Sort node →
  `Parallel Seq Scan`; pgvector only uses HNSW when `ORDER BY` is distance-only + `LIMIT k`.

## Dependency graph

```
B-5(done) ──► B-11            B-7(done) ──► B-8 ──► B-9 (optional, one axis at a time, last)
B-7(done) ··► B-2 (hosted-model disambiguation enabler)
composer.py chain (serialize): B-10 ─► B-4 ─► B-2
frontend shapes chain (serialize): B-10 ─► B-3
B-11 independent · B-8 independent of B-10/B-3
```

## Conflict matrix (shared file → never run these concurrently)

| Shared file | Items that touch it | Rule |
|---|---|---|
| `backend/agents/composer.py` | B-10, B-4, B-2 | serialize all three (B-10 → B-4 → B-2) |
| `frontend/src/components/shapes/` | B-10 (broad), B-3 (SupportShape) | serialize (B-10 first; it may restructure shapes) |
| `backend/agents/router.py` | B-2 (only open owner; ex-B-1) | single owner |
| `backend/retrieval/schema.py` | B-9 (dim) | single owner (B-5's index DDL already merged) |
| `backend/app/config.py` | B-9 | single owner (B-7's keys already merged) |
| `backend/eval/` | B-8, B-9 | serialize (B-9 strictly after B-8) |

File-disjoint pairs safe to run concurrently: **B-11 ∥ B-8 ∥ B-10** (vector_store.py vs
eval/+docs vs composer/main/frontend — no shared file). B-11 touches nothing else.

## Runtime caveat (shared local DB / `chunks`)

- **The 225k embed (P4) is already done**, so Wave 1 has no competing embed run. B-11 only
  changes the query *form* — no DB mutation; safe alongside anything.
- **Measurement ordering:** B-8's latency p50/p95 is measured through the retrieval path.
  **Land B-11 before B-8's benchmark run** so the study's latency reflects the fixed
  (index-hitting) serving query, not the seq-scan. They can be *developed* in parallel; gate
  B-8's timed run on B-11 being merged.
- **B-9 recreates `chunks.embedding vector(N)` and re-embeds everything** — run strictly alone,
  after B-8, as the only DB-mutating item left. Query-time embedder must match the stored one.

## Wave plan

**Wave 1 — realize the shipped speedup + the headline study + SQL-answer quality (3 parallel, file-disjoint).**
- Track A: **B-11** — split the query: inner `ORDER BY embedding <=> %s LIMIT k` (hits HNSW),
  outer re-sort by `score DESC, id` for deterministic ties. Re-run `scratchpad/bench_b5.py`
  against the production query form as acceptance (target ~0.5 ms p50 vs ~61 ms). **Do this first.**
- Track B: **B-8** — model-comparison study over the 6 target models via B-7; hold embeddings/
  retrieval/SQL fixed, vary only generation. Develop in parallel, but run its timed benchmark
  only after B-11 merges.
- Track C: **B-10** — structured SQL rows/columns through `AnswerResult`/API as a typed block;
  render table/chart in role shapes instead of regex-scraping prose. Keep grounding/citation
  invariants.
- Merge order: B-11 → (B-8 timed run) ; B-10 merges independently.

**Wave 2 — UX correctness on the composer + support shape (serialize where files overlap).**
- Track A (`composer.py`, serial): **B-4** (trivial word-boundary truncate + "…") → **B-2**
  (free-path history: prepend recent turns to router/composer input; B-7's hosted model is the
  disambiguation enabler). B-4 first because it is a one-liner and de-risks the shared file.
- Track B: **B-3** (SupportShape FIX/ISSUE tag) — run after B-10 merges (B-10 may restructure
  shapes); file-disjoint from Track A, so concurrent with B-4/B-2.

**Wave 3 — optional experiment, isolated.**
- **B-9** embedder bake-off: alone, after B-8, one axis at a time (recreates vector dim +
  re-embeds). Keep strictly separate from B-8 so only the embedder varies.

Merge order across waves: 1 → 2 → 3. Within a wave, per-track order as noted.

## Rationale (top tier)

- **B-11 (#1):** highest leverage open item. B-5 shipped an HNSW index and P4 embedded 225k
  vectors, but the live `review_rag`/vector path still seq-scans all of them — the ~125× win is
  built but not delivered. One-file, surgical (inner distance-only ANN + outer deterministic
  re-sort), with a ready benchmark harness as acceptance evidence. Lands the value already paid for.
- **B-8 (#2):** the headline portfolio deliverable — turns "model choice by assertion" into
  evidence. Unblocked now that B-7 merged; large but mechanical. Gate its timed run on B-11.
- **B-10 (#3):** the most user-visible correctness gap (years plotted as values, prose re-scraped
  for a number, no real chart); independent of #1/#2, so it fills the third parallel track.

## Flags / open questions for the human

1. **B-11 before B-8's timed run?** Recommended — otherwise B-8's latency numbers bake in the
   seq-scan. Confirm you want B-11 gated ahead of B-8's benchmark (dev can still overlap).
2. **B-2 is a real design decision, not a patch.** M5 deliberately kept memory off the free path.
   B-7's hosted open-weight model is now available as the honest disambiguation enabler — confirm
   you want the LLM-path fix (vs a narrower rule/composer history patch). Ranked #4, Wave 2.
3. **B-9 is optional** (BACKLOG marks it so). It is the only item that recreates the vector
   dimension + forces a full re-embed. Kept last and isolated; confirm whether to schedule it at all.
