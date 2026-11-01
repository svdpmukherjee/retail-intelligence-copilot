# BACKLOG_PLAN.md — delivery blueprint (Product Owner)

Regenerated 2026-11-01 (full re-rank, no human focus). Source: `context/BACKLOG.md`.
Advice to the orchestrator — each item runs as its own `/change`; the human approves each.
Severity = impact-if-it-occurs (from BACKLOG); **priority** = severity + business value +
effort + risk + dependencies, so the rank deliberately diverges from severity.

Current reality (PROJECT / CURRENT_TASK / git / DECISIONS): M1–M8 + v2/v3 DONE, **local-only**
stack (Azure/Databricks plane parked). **The entire previous top wave has shipped** —
`B-5`, `B-6`, `B-7` (Wave 1) and `B-8`, `B-10`, `B-11`, `B-12` (Wave 2) are all DONE+merged
(`main`=`f12af36`), plus data-op P4 (225k full-corpus local embed). `B-1` was DROPPED (resolved).
**Genuinely open items now: B-2, B-3, B-4, B-9** — four items, all unblocked. This is the UX-/
quality-correctness tail plus one optional experiment; no HIGH-leverage infra work remains.

## Ranked table

| Rank | Item | Severity | Value | Effort | Risk | Depends on | Wave | Track | File domain | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | B-3 support per-line FIX/ISSUE mislabel | MED | MED-HIGH | S | L | — (B-10 done) | 1 | B | `frontend/src/components/shapes/SupportShape.tsx` | **Ready — start first** |
| 2 | B-2 follow-ups ignore history on free path | HIGH | MED | M | MED | B-4 (file order); B-7 enabler (done) | 1 | A | `backend/agents/router.py`, `backend/agents/composer.py`, memory `context` wiring | Flagged (design decision) |
| 3 | B-4 citation snippet truncates mid-word | LOW | LOW-MED | S | L | — | 1 | A | `backend/agents/composer.py` (`_snippet` L91 + quote L115) | Ready — do before B-2 |
| 4 | B-9 embedder bake-off (optional) | MED | MED | L | MED | — (keep after/ separate from model studies) | 2 | A | `backend/retrieval/embeddings.py`, `app/config.py`, `backend/retrieval/schema.py` (dim), `backend/eval/` | Deferred/optional |
| — | B-1 vague "why?" false-routes to sql_rag | MED | — | — | — | — | — | — | `backend/agents/router.py` | **DROPPED (resolved) — closed in BACKLOG** |

## Changed since the previous plan

- **B-8 / B-10 / B-11 / B-12 → DONE+merged** (`f12af36` and prior). The whole previous
  top wave (B-11 ∥ B-8 ∥ B-10) is closed; B-12 safety fix + data-op P4 recovery also done.
- **B-3 fully unblocked.** Its old "after B-10 (shared shapes)" dependency is gone — B-10
  merged and even added `SqlTable.tsx`; B-3 touches only `SupportShape.tsx`, file-disjoint
  from everything, so it is now the cleanest ready win and is ranked #1 by priority.
- **Plan shrinks from 7 open items to 4.** Only the UX/quality tail (B-2, B-3, B-4) plus the
  optional B-9 embedder experiment remain. No remaining HIGH-value infra item.

## Dependency graph

```
composer.py chain (serialize): B-4 ─► B-2   (B-7 hosted-model enabler already merged, feeds B-2)
B-3  — independent (frontend SupportShape only)
B-9  — independent, optional, DB-mutating, run alone and last
```

## Conflict matrix (shared file → never run these concurrently)

| Shared file | Items that touch it | Rule |
|---|---|---|
| `backend/agents/composer.py` | B-4, B-2 | serialize (B-4 → B-2); B-4 is a one-liner that de-risks the shared file |
| `backend/agents/router.py` | B-2 only | single owner (ex-B-1 closed) |
| `frontend/src/components/shapes/SupportShape.tsx` | B-3 only | single owner |
| `backend/retrieval/schema.py` / `embeddings.py` / `app/config.py` / `backend/eval/` | B-9 only | single owner |

File-disjoint pairs safe to run concurrently: **B-3 ∥ (B-4→B-2 chain)** — frontend SupportShape
vs backend composer/router share no file. B-9 is isolated but DB-mutating (see caveat).

## Runtime caveat (shared local DB / `chunks`)

- **B-2, B-3, B-4 do no DB mutation** — safe to run in any order the file-conflict matrix allows.
- **B-9 recreates `chunks.embedding vector(N)` and re-embeds all 225k rows** — the only
  DB-mutating item left. Run it strictly **alone**, and the query-time embedder must match the
  stored one. The local P4 corpus (~949 MB) was destroyed once already; the B-12 guard now
  protects the *test* DB, but B-9 deliberately rewrites the *real* corpus, so treat it as a
  logged, intentional rebuild, not a casual run.

## Wave plan

**Wave 1 — the UX/quality-correctness tail (2 parallel tracks, file-disjoint).**
- Track A (`composer.py`, serial): **B-4** (word-boundary truncate + "…" at `_snippet` L91 and
  the `quote` cut at L115) → **B-2** (free-path history: prepend recent turns to router/composer
  input; B-7's hosted open-weight model is the honest disambiguation enabler). B-4 first — it is
  a one-liner and de-risks the file B-2 then rewrites.
- Track B: **B-3** (SupportShape FIX/ISSUE tag — make it reliable or drop the per-line tag and
  keep the "Governing policy" callout). Isolated frontend file; concurrent with Track A.
- Merge order: within Track A, B-4 → B-2; B-3 merges independently.

**Wave 2 — optional experiment, isolated.**
- **B-9** embedder bake-off: alone, DB-mutating (recreates vector dim + re-embeds 225k), one axis
  at a time. Schedule only if the human wants the retrieval-quality comparison; otherwise skip.

## Rationale (top tier)

- **B-3 (#1):** priority ≠ severity. Only MEDIUM severity, but S effort, low risk, fully
  unblocked, file-isolated, and the most recruiter-visible correctness bug (policy lines
  mislabelled "FIX") in the live demo. Highest value-per-effort of the open set — start here.
- **B-2 (#2):** the only HIGH-severity open item and the biggest *functional* gap (vague
  free-path follow-ups like "why?" ignore conversation history). Ranked below B-3 because it is a
  flagged design decision (M5 deliberately kept memory off the free path), M effort, MED risk,
  and its fully honest fix leans on the hosted-model path — so today's free-path deliverable is
  partial. Execute it after B-4 in the composer chain.
- **B-4 (#3):** LOW severity and low value on its own, but a trivial word-boundary one-liner that
  must land before B-2 to de-risk the shared `composer.py`; cheap to fold into Wave 1 Track A.

## Flags / open questions for the human

1. **B-2 is a real design decision, not a patch.** M5 deliberately kept memory off the free path;
   B-7's hosted open-weight model is available as the honest disambiguation enabler, but the cloud
   plane is parked. Confirm you want the LLM-path fix now (vs a narrower rule/composer history
   patch, vs deferring B-2 until a hosted model is live again). Assumption made: ranked #2/Wave 1
   assuming you want it addressed this round via B-7.
2. **B-3 scope choice.** Two acceptable fixes in BACKLOG — (a) make the per-line tag reliable
   (confident-only) or (b) drop the per-line tag and keep the "Governing policy" callout. Assumed
   either is fine; flag which you prefer at `/change` time.
3. **B-9 is optional** (BACKLOG marks it so) and the only item that recreates the vector dimension
   + forces a full re-embed of the real corpus. Kept last and isolated; confirm whether to
   schedule it at all.
