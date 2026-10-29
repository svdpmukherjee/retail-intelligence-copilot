# BACKLOG.md — deferred engineering/UX work

Items parked deliberately, to be picked up **after the cloud data-pipeline
operationalization** (Azure + Databricks) is complete. Each has symptom → root
cause → fix → where, so it can be run the usual command-driven way without
re-deriving context. Pure cosmetic/visual polish lives in `design/BACKLOG.md`;
this file is behaviour + UX correctness.

Found during live verification of the M8 v3 build (support role, two-turn
conversation: "What is the return policy?" → "why?"), 2026-10-29.

## B-1 — Vague follow-up ("why?") false-routes to `sql_rag` — MEDIUM

- **Symptom:** a bare "why?" follow-up routed to `sql_rag`, the SQL query failed
  (degraded gracefully), and it answered from an irrelevant Electronics review —
  a useless answer to what was a follow-up about the return policy.
- **Root cause:** the D-2 rule-first router matches the "why-changed → `sql_rag`"
  keyword pattern on a bare "why?", which is a false positive (that rule is for
  "why did sentiment/volume change?").
- **Fix:** tighten the rule so "why" only routes to `sql_rag` when paired with a
  change/trend word (change, increase, drop, trend, more, fewer, …), not on a
  bare "why?". Run as a `/change` (routing-rule revision).
- **Where:** `route()` keyword patterns in `backend/agents/router.py`.

## B-2 — Follow-ups don't use conversation history on the free path — HIGH

- **Symptom:** the thread is stored and now *displayed* (v3), but a vague
  follow-up ("why?") is routed and answered on the bare word, with no awareness
  of the previous turn.
- **Root cause:** documented M5 decision — "in pure free mode the rule-based
  router and extractive composer don't yet *use* loaded history." Memory
  influences only the LLM path.
- **Fix:** on the free path, prepend recent turns to the router/composer input so
  a vague follow-up inherits prior intent/subject. NOTE: M5 deliberately kept
  memory off the free path, so this is a real design decision, not just a patch —
  run as a `/change`. The fuller, more honest fix is the **Azure LLM path**, where
  the router can disambiguate "why?" against context; revisit this item *after*
  operationalization when the stronger model is live.
- **Where:** `backend/agents/router.py`, `backend/agents/composer.py`, memory
  context wiring (M5 `context` kwarg).

## B-3 — Support-shape per-line tag ("FIX"/"ISSUE") mislabels content — MEDIUM

- **Symptom:** every return-policy extract was tagged `FIX`; the review line in
  turn 2 was tagged `ISSUE`. Policy statements are not "fixes" — the tag is
  confusing to a recruiter reading the demo.
- **Root cause:** the support role shape assigns an `ISSUE`/`FIX`/`POLICY` tag per
  answer line via a heuristic that is unreliable on extractive/doc content.
- **Fix:** either make the tag reliable (only tag when the classification is
  confident) or drop the per-line tag and keep the "Governing policy" callout,
  which reads correctly. A UI fix — can fold into a v3 follow-up or a `/change`.
- **Where:** the v3 support-shape component under `frontend/src/components/`.

## B-4 — Citation snippet truncates mid-word — LOW

- **Symptom:** citation [3] ended "…eligible only for a partial re" — severed
  mid-word, no ellipsis.
- **Fix:** truncate snippets on a word boundary and append "…".
- **Where:** the citation/snippet render in `frontend/src/components/` (evidence
  panel + inline citation).
