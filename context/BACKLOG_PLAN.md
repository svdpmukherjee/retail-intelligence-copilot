# BACKLOG_PLAN.md — delivery blueprint (Product Owner)

Regenerated 2026-11-02 (full re-rank — productionization plane added). Source: `context/BACKLOG.md`.
Advice to the orchestrator — each item runs as its own `/change`; the human approves each.
Severity = impact-if-it-occurs (from BACKLOG); **priority** = severity + business value +
effort + risk + dependencies. Never copy severity as the rank.

## Current reality

M1–M8 + v2/v3 DONE, **local-only** stack (Azure/Databricks plane parked; data-op P4 local embed
of 225k reviews + 79 docs live in pgvector). The old Wave-1 UX/quality tail is shipped and B-1 is
dropped:

- **B-2** free-path history — ✅ DONE+merged (`868e2a4`).
- **B-3** support per-line FIX/ISSUE tag dropped — ✅ DONE+merged (`d6c80d4`).
- **B-4** citation word-boundary truncate — ✅ DONE+merged (`484e5ce`).
- **B-5..B-8, B-10..B-12** — ✅ DONE+merged (prior waves).
- **B-1** vague "why?" false-route — ❌ DROPPED (root cause no longer exists).

**B-13 shipped 2026-11-02** (observability plane, `/change`, Option A). **Two items remain open.**
**B-14** (audit admin view) is now the next unblocked item — it shares `backend/app/main.py` with
B-13, so it was correctly held until B-13 landed. One carried item remains: the optional,
DB-mutating **B-9** (embedder bake-off). Both productionization-plane items (B-13 ✅, B-14) give
the operator-facing internals their proper homes, per `.claude/rules/ux-surface.md`.

**Downstream dependent (NOT a backlog item, NOT ranked here):** the **chat UI persona redesign**
runs as **Design Track `/design` iteration-4**, not a `/change`. B-13 and B-14 unblock it — they
build the internals' new homes so the redesign can strip metrics/ids/routing out of the chat
without losing them ("build the data's new homes before stripping the chat"). It appears below
only as a dependent, never as a ranked row.

## Ranked table

| Rank | Item | Severity | Value | Effort | Risk | Depends on | Wave | Track | File domain | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | B-13 Observability plane (Langfuse tracing) | HIGH | HIGH | M–L | MED | — | 1 | solo | **Built via Option A (ADR 2026-11-02): central seam in `backend/observability/tracing.py` + `backend/agents/pipeline.py` + `backend/app/main.py` (lifespan flush) + `backend/app/config.py` + `backend/.env.example` + `backend/pyproject.toml`. Agent files NOT edited** (diverges from the per-agent file domain first assumed here) | **✅ DONE 2026-11-02** |
| 2 | B-14 Audit admin view (read-only over `audit_log`) | MED | MED–HIGH | M | LOW–MED | — (soft: after B-13 for `main.py`) | 2 | solo | `backend/app/main.py` (new read endpoint), `backend/governance/audit.py` (read method on `AuditStore`), new admin view under `frontend/src/` (apart from chat shapes) | **TODO — run after B-13** |
| 3 | B-9 Embedder bake-off (optional) | MED | MED (flagged) | L | MED | — | 3 | solo | `backend/retrieval/embeddings.py`, `backend/retrieval/schema.py` (vector dim), `backend/app/config.py` (`EMBEDDING_MODEL_FREE`), `backend/eval/` | **Optional / cost-gated / DB-mutating — run alone, only on human go-ahead** |
| — | B-2 / B-3 / B-4 | H/M/L | — | — | — | — | — | — | (shipped) | ✅ DONE+merged |
| — | B-1 vague "why?" false-route | MED | — | — | — | — | — | — | `backend/agents/router.py` | ❌ DROPPED (resolved) |
| — | Chat UI persona redesign | — | — | — | — | **B-13 + B-14** | — | — | `frontend/src/` chat shapes | **NOT a backlog item — Design Track `/design` iteration-4; unblocked by B-13 + B-14** |

## Dependency graph

```
B-13  ──(unblocks)──┐
                    ├──> chat UI persona redesign  (Design Track /design iteration-4, NOT a /change)
B-14  ──(unblocks)──┘

B-13 ── no hard code dependency on B-14.  Human order B-13 → B-14 honored
        (both are "homes"; B-13 is HIGH + wider blast radius, B-14 is a read-only
        surface over the existing audit_log — natural to land the tracing plane first).

B-14 ── soft ordering only: shares backend/app/main.py with B-13, so it must land
        AFTER B-13 merges to avoid a main.py conflict. No functional dependency.

B-9  ── independent, optional, DB-mutating (recreates vector dim + re-embeds the real
        corpus). Blocks nothing, blocked by nothing.
```

No hard dependency forces a reorder, so the human's **B-13 → B-14 → (redesign)** order stands.

## Conflict matrix (shared file → never run these concurrently)

| Shared file | Items that touch it | Rule |
|---|---|---|
| `backend/app/main.py` | **B-13** (per-request trace lifecycle) + **B-14** (new audit read endpoint) | **Serialize B-13 and B-14** — both edit the FastAPI app module. Decisive reason they are separate waves. |
| `backend/app/config.py` | **B-13** (Langfuse flag + keys) + **B-9** (`EMBEDDING_MODEL_FREE` / vector dim) | **Serialize B-13 and B-9** — both add/alter `Settings`. |
| `backend/governance/audit.py` | B-14 only | single owner — no contention. |
| `backend/agents/*` + `pipeline.py` | B-13 only | single owner — no contention. |
| `backend/retrieval/*`, `backend/eval/` | B-9 only | single owner — no contention. |
| `frontend/src/` (admin view) | B-14 only (new surface, apart from chat shapes) | single owner. The iteration-4 redesign touches chat shapes later, not now. |

**File-disjoint pair:** B-14 and B-9 share no file, so they *could* run concurrently in principle.
They are NOT parallelized here because (a) B-9 is optional/cost-gated and ranked last, and (b) the
runtime caveat below serializes any DB-mutating run. Flagged as the only theoretical parallel track
if B-9 is ever greenlit alongside B-14.

## Runtime caveat (shared local DB)

- **B-9 is the only DB-mutating item** — it recreates `chunks.embedding vector(N)` (dimension
  changes with the embedder) and **re-embeds all ~225k reviews + 79 docs**; the query-time embedder
  must then match the stored one. Run it **strictly alone** as a logged, intentional corpus rebuild.
  The local P4 corpus (~949 MB) was destroyed once by a test fixture; the B-12 guard protects the
  *test* DB, but B-9 overwrites the *real* `rag` corpus by design.
- **B-13 and B-14 do not mutate the corpus.** B-13 reads the pipeline to emit spans (keep it
  batch/async, off the per-query latency path); B-14 only *reads* `audit_log`. Neither collides on
  DB writes with the other, but both still serialize via the `main.py` file conflict above.
- **Cost-gate (`CLAUDE.md`):** B-9's local re-embed is $0 on the free embedder, but any
  hosted/open-weight embedder candidate spends — log in `COST.md`. B-13's Langfuse is an external
  provider: keep it **feature-flagged off by default and gated** (like Azure/OpenRouter); a hosted
  Langfuse endpoint is only exercised on explicit go-ahead. Self-hosted/local Langfuse is $0.

## Wave plan

**Wave 1 — B-13 (solo).** Add Langfuse behind the provider seam, feature-flagged off by default,
instrumenting router → retrieval → composer → LLM as spans (timings, tokens, cost) with a per-request
trace lifecycle in `main.py`. Operator plane only — PII-redacted, nothing leaks to the chat UI,
never on the latency path. Merge before Wave 2 (frees `main.py` + `config.py`).

**Wave 2 — B-14 (solo), after B-13 merges.** Role-gated, read-only API endpoint over the existing
`audit_log` (no schema change, no new writes) + a small admin surface under `frontend/src/`, kept
apart from the chat shapes. Access control enforced server-side, same posture as retrieval.

**Wave 3 — B-9 (solo, conditional).** Only on explicit human go-ahead: recreate the vector dim,
re-embed the full corpus, measure recall@k / MRR of MiniLM vs open-weight candidates via the M7 gate.
One axis at a time (embedder only; generation model fixed — keep separate from B-8). Runs strictly
alone (DB-mutating).

**Merge order:** B-13 → B-14 → (B-9 if greenlit). After B-13 + B-14 are in, the chat UI persona
redesign can start as `/design` iteration-4.

## Rationale (top tier)

- **B-13 (#1):** HIGH severity + HIGH value. It is the observability plane the new `ux-surface.md`
  rule explicitly points to, it carries the job-ad "observability/tracing" skill, and together with
  B-14 it is a precondition for the chat redesign (internals need a home before they are stripped
  from the chat). Wider blast radius (agent spans + pipeline + main + config) than B-14, so landing
  it first and alone keeps the risky instrumentation isolated. Honors the human's stated order.
- **B-14 (#2):** MEDIUM severity, MEDIUM–HIGH value, LOW–MED risk (read-only, no DDL). It makes the
  already-written `audit_log` visible through a governed admin surface — the governance/auditability
  story becomes demonstrable. Ranked below B-13 both by the human's order and because it shares
  `main.py` with B-13 (must land after it), not because it is blocked functionally.
- **B-9 (#3):** optional, cost-gated, DB-mutating; ranked last deliberately. Priority ≠ "do it" — see
  flags. It is the one item that rewrites the live corpus, so it only runs on explicit go-ahead.

## Flags / open questions for the human

1. **B-13 vs B-14 order — no hard dependency found; human order honored.** Neither item functionally
   depends on the other's code. The only coupling is the shared `backend/app/main.py`, which forces
   *serialization* (not a specific direction). I kept **B-13 → B-14** per your stated order and because
   B-13 is HIGH / wider-blast-radius while B-14 is a thin read-only surface. No deviation made.
2. **B-14 shows exactly what the chat must not.** By design B-14 surfaces ids, cost, routing, tokens —
   the internal fields `ux-surface.md` bars from the chat. Confirm the admin surface is firmly
   **role-gated (admin-scoped) and server-enforced**, kept out of the chat shapes, so the
   surface-boundary rule holds. (Assumption: enforced server-side at the endpoint, same posture as
   retrieval — stated in the item.)
3. **B-13 Langfuse must stay off the latency path and gated.** Assumption: feature-flagged off by
   default, batch/async span export, self-host or gated-hosted. Confirm whether a hosted Langfuse is
   in scope (spend → `COST.md`) or local/self-hosted only ($0).
4. **Is B-9 worth the re-embed given B-8 already ran?** B-8's live 6-model study found answer quality
   saturated and model-independent (grounded-path + citation-validity 1.00 — "governance does the
   work"). B-9 varies a *different* axis (embedder → retrieval recall@k / MRR, not answer quality), so
   it is not redundant — but if end-to-end quality is already governance-bound, confirm a better
   embedder moves a metric a recruiter cares about before paying the full-corpus re-embed. **Assumption:
   B-9 stays optional/deferred unless you explicitly want the retrieval-quality comparison as a
   portfolio artifact.**
5. **B-9 value is ambiguous — stated, not guessed.** Scored MED-flagged because its payoff depends on
   whether a retrieval-quality delta is a story you want to tell. Flagging rather than guessing silently.
6. **Only theoretical parallel track:** B-14 ‖ B-9 are file-disjoint, but not parallelized here (B-9 is
   optional/last and DB-mutating → serialize). Noted only so the option is visible.
7. **Chat UI persona redesign is deliberately absent from the ranked table** — it is Design Track
   `/design` iteration-4, not a backlog `/change`. It is listed only as the downstream dependent that
   B-13 + B-14 unblock.
