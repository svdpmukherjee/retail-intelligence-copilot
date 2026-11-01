# BACKLOG_PLAN.md — delivery blueprint (Product Owner)

Regenerated 2026-11-01 (full re-rank, no human focus given). Source: `context/BACKLOG.md`.
Advice to the orchestrator — each item still runs as its own `/change`; the human approves
each. Severity is impact-if-it-occurs (from BACKLOG); **priority** = severity + business
value + effort + risk + dependencies, so the rank deliberately diverges from severity.

Current reality (from WORKLOG / DECISIONS): M1–M8 + M8 v2/v3 serving UI DONE; data-plane
ops P1–P3 DONE (Azure Postgres up, real local-Spark medallion ETL published Gold→Blob);
**P4 = embed the corpus for real is the next data-plane op** (a data op, not a backlog
item). **Human decision 2026-11-01: work the LOCAL stack only — the Azure/Blob plane is
parked, so P4 and B-5/B-6 target the local pgvector `chunks` table.** The 2026-11-01 batch
(B-5…B-10) is the retrieval-sharpness + model-evaluation study on the local stack; B-1…B-4
are older UX-correctness items from M8 v3 live verification.

## Ranked table

| Rank | Item | Severity | Value | Effort | Risk | Depends on | Wave | Track | File domain | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | B-5 ANN index on `embedding` | HIGH | HIGH | S | L-M | — (pairs w/ P4) | 1 | A | `backend/retrieval/schema.py`, `vector_store.py` | Ready |
| 2 | B-6 streaming indexer (no full RAM load) | MED | MED-HIGH | M | L | — (pairs w/ P4) | 1 | B | `backend/retrieval/index_reviews.py` | **DONE 2026-11-01** |
| 3 | B-7 OpenRouter generation provider | HIGH | HIGH | M | L-M | — | 1 | C | `backend/agents/llm.py`, `app/config.py`, `.env.example` | Ready |
| 4 | B-8 controlled model-comparison study | HIGH | HIGH | L | MED | **B-7** | 2 | A | `backend/eval/`, golden-set fixtures, `docs/` | Blocked on B-7 |
| 5 | B-10 structured SQL result passthrough | MED | MED-HIGH | M | L-M | — | 2 | B | `backend/agents/composer.py`, `app/main.py`, `frontend/src/api/types.ts`, `answer.ts`, `components/shapes/` | Ready |
| 6 | B-3 support per-line FIX/ISSUE mislabel | MED | MED | S | L | — | 3 | B | `frontend/src/components/shapes/SupportShape.tsx` | Ready |
| 7 | B-4 citation snippet truncates mid-word | LOW | LOW-MED | S | L | — | 3 | A | `backend/agents/composer.py` (`_snippet`), `frontend/src/components/EvidencePanel.tsx` | Ready (see note) |
| 8 | B-2 follow-ups ignore history on free path | HIGH | MED | M | MED | B-7 (enabler), B-1-area | 3 | A | `backend/agents/router.py`, `composer.py`, memory wiring | Flagged |
| 9 | B-9 embedder bake-off (optional) | MED | MED | L | MED | after B-8 (one axis at a time) | 4 | A | `backend/retrieval/embeddings.py`, `app/config.py`, `schema.py` (dim), `backend/eval/` | Deferred |
| — | B-1 vague "why?" false-routes to sql_rag | MED | — | — | — | — | — | — | `backend/agents/router.py` | **DROP — effectively resolved** |

## Stale / resolved by shipped work

- **B-1 — DROP (root cause no longer exists).** The `sql_rag` rule in `router.py` already
  requires `\bwhy\b.*\b(chang|drop|increas|decreas|declin|fell|fall|rose|rise|spik|dip)\b`
  (change-word-paired, from the D-2 rule-first routing work). A bare "why?" matches **no**
  rule, so it never routes to `sql_rag` — it falls through to the LLM/`review_rag` default.
  B-1's specific false-route is fixed. The *remaining* symptom (a bare "why?" gives a
  useless answer because the free path has no history awareness) is **B-2's** territory, not
  a routing-rule bug. Recommend: close B-1; fold any residue into B-2.
- **B-4 — "where" has moved.** Snippets are now produced server-side in
  `composer._snippet()` (`redact(" ".join(text.split())[:MAX_QUOTE_CHARS])`), since M8 v2
  moved redacted snippets to the backend. The mid-word truncation still exists but the fix
  locus is **backend `composer.py`** (word-boundary truncate + append "…"), not the frontend
  render as BACKLOG states. The frontend `EvidencePanel.tsx` only displays `shown.snippet`.

## Dependency graph

```
B-7 ──► B-8 ──► (B-9, one axis at a time, isolated last)
B-5 ─┐
B-6 ─┴─(pair with data-op P4: full-corpus embed)
B-10  (independent)   B-3 (independent)   B-4 (independent)   B-2 (benefits from B-7)
```

## Conflict matrix (shared file → never run these concurrently)

| Shared file | Items that touch it | Rule |
|---|---|---|
| `backend/retrieval/schema.py` | B-5, B-9 | serialize (B-9 recreates `embedding vector(N)` dim) |
| `backend/app/config.py` | B-7, B-9 | serialize (B-9 is last anyway) |
| `backend/agents/composer.py` | B-10, B-4, B-2 | serialize all three |
| `backend/agents/router.py` | B-2 (and ex-B-1) | single owner |
| `backend/eval/` | B-8, B-9 | serialize (B-9 after B-8) |
| `frontend/src/components/shapes/` | B-10, B-3 | serialize (B-10 touches shapes broadly; B-3 edits SupportShape) |

All other items are file-disjoint.

## Runtime caveat (shared local DB / lake)

B-5, B-6, B-9 and data-op **P4** all mutate the one local pgvector `chunks` table (index
build, full-corpus embed, re-embed) and B-8/B-9 eval runs read that same index. **The code
changes can be developed in parallel, but the DB-mutating *runs* must be serialized** — only
one embed/index/eval run against the lake at a time. B-9 changes the embedding **dimension**,
forcing a `chunks` table recreate + full re-embed — run it strictly alone, after B-8.

## Wave plan

**Wave 1 — retrieval readiness + study enablement (3 parallel tracks, file-disjoint).**
- Track A: **B-5** (ANN/HNSW index, cosine op class matching the query).
- Track B: **B-6** (stream the Gold read + embed/upsert per batch).
- Track C: **B-7** (OpenRouter adapter behind the seam; no DB run).
- *Run order (DB-mutating steps serialized):* land B-6 first so the embed is memory-safe,
  then B-5, then run data-op **P4** (full-corpus embed) once — B-5+B-6 exist precisely to
  make P4 scale cleanly, so do them *before* embedding 225k. B-7 merges independently
  (no DB run). Capture p50/p95 + recall@k before vs after via the M7 gate — that before/after
  is B-5's deliverable.

**Wave 2 — the headline study + the SQL-answer quality fix (2 parallel tracks).**
- Track A: **B-8** (model comparison over the 6 target models; needs B-7). DB-read run —
  serialize against any Wave-1 embed still in flight.
- Track B: **B-10** (structured SQL passthrough to a typed data block + table/chart render).
  File-disjoint from B-8 (composer/main/frontend vs eval/) → safe to run concurrently.

**Wave 3 — UX correctness polish (serialized where they share files).**
- Track A: **B-4** then **B-2** on `composer.py` (B-4 first, trivial; B-2 is the larger
  router+memory change). B-2 also wants B-7's hosted model as the disambiguation enabler.
- Track B: **B-3** (SupportShape tag) — independent, any time after Wave-2 B-10 merges
  (B-10 may restructure the shapes).

**Wave 4 — optional experiment, isolated.**
- **B-9** embedder bake-off: alone, after B-8, one axis at a time (recreates the vector dim +
  re-embeds everything). Keep strictly separate from B-8 so only the embedder varies.

Merge order across waves: 1 → 2 → 3 → 4. Within a wave, merge order is noted per track above.

## Rationale (top tier)

- **B-5 (#1):** smallest change (one DDL index) with the highest leverage right now — it is
  the precondition for P4's 225k-vector embed to query in sub-linear time, and its before/after
  latency/recall numbers via the M7 gate are themselves a portfolio deliverable.
- **B-6 (#2):** without streaming, the full-corpus embed OOMs (`to_pylist()` materialises every
  review); it directly unblocks the imminent P4 run and pairs with B-5.
- **B-7 (#3):** unblocks B-8, the headline model-comparison study; a self-contained adapter
  behind the existing seam, gated like Azure, so low risk.
- **B-8 (#4):** turns "model choice by assertion" into evidence — the defensible recruiter
  story; large but mechanical once B-7 lands.

## Resolved decisions (human, 2026-11-01)

- **Local only — cloud dropped for now.** P4 and B-5/B-6 target the **local pgvector**
  `chunks` table; B-5's ANN index is built there. The Azure Postgres/Blob plane stood up in
  P1–P3 is **parked** (maybe later, not now). No ranking change — this fixes *where* the
  index and embed land. Any cloud-targeted embed is out of scope until re-opened.
- **B-2 stays at Wave 3, Track A (after B-7).** Confirmed: B-7's hosted open-weight model is
  its disambiguation enabler, so B-2 runs after it rather than shrinking to a model-free
  router/composer patch.

## Remaining flag for the human

- **B-9 is optional** (BACKLOG marks it so). Kept last and isolated because it is the only
  item that recreates the vector dimension + forces a full re-embed.
