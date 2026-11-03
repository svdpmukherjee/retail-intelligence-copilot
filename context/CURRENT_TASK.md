# Current state — remediation documented and committed

Updated 2026-11-03. This file is the current snapshot; older WORKLOG/module entries
are dated history. Start with AGENTS.md and CLAUDE.md, then this file,
PROJECT.md and RESUME_NEXT_SESSION.md. Do not reconstruct current status from an
old “uncommitted”, “no paid calls” or “stages not started” paragraph.

## Current objective and authorization

The user requested a complete documentation audit of changes since GitHub
`ec0ef266ca2d1bfa4094e19a9dbfaa1dd4006738`, then concise commits without co-author
trailers and a push. Publishing is authorized on `plan/answer-quality-remediation`;
merging to main, deployment and quality-stage acceptance are separate decisions.
Documentation audit is complete; no new implementation task is active. Quality
review is the next user decision. Publication is on the feature branch only. The branch was fast-forwarded to `ec0ef26` before committing: it had the
same tree as the previous local `65665dd`, so no source changes were overwritten.

## Implemented state

- Stage 1 baseline accepted and preserved. Stage 2 bounded routing/SQL correction
  accepted, without declaring complete answer quality.
- Stage 3 provenance/normalization/token chunks/immutable evidence bundles built
  and fixture-verified, awaiting review. Real backfill/cutover remains gated;
  `EVIDENCE_BUNDLE_PATH` is opt-in, not activated in the recorded serving checks.
- Practical Stage 4 workaround and conversational repairs implemented, awaiting
  user quality review. Stage 5/model bake-offs have not started.
- Entry planner receives capabilities and active-plan context; validates typed
  conditions, role scope and independent questions; retains clarification state.
  Product prices/discovery operate at ASIN/category grain, not review-row grain.
- SQL-selected product explanations read bounded existing Silver reviews and
  verify all-review counts/means. Ordinary semantic review search remains sampled.
- Deterministic SQL summaries, grouped citations, shared safe Markdown, full
  redacted source passages, honest empty/partial states and contextual suggestion
  buttons are integrated. Final synthesis retains the full retrieved evidence pool.

## Verification and limits

The preceding implementation session recorded 138 focused tests, frontend checks,
71 real browser turns across 27 distinct questions (including failed iterations and
rechecks), and 25 named latest-outcome checks with independent Gold aggregates.
See the documentation-audit verification record in docs/answer-quality-status.md
for the newer combined pre-publication test result (**177 passed**); do not add historical suite
counts together or call 71 turns 71 final passes.

Some Pet Supplies/policy drafts still fall back to source excerpts after rejected
synthesis/one bounded repair. Citation validity is not factual support. No complete
semantic faithfulness, full-corpus recall, physical-device accessibility or arbitrary
SQL quality pass is claimed. The existing docs-only CI eval remains separate.

The last live read-only check found 225,000 review chunks / 79 document chunks,
unchanged review-ID checksum, and Gold structured/reviews + Silver Delta versions1.
No ETL, reindex, serving schema/data migration or model downloads occurred.
Additional provider-reported repair-run cost $0.010445375; cumulative remediation
reported $0.013769129. Four failed calls have no cost report; conservative retained
reservations were $0.42382848 under the original $2 authorization. No new paid calls
are needed for this documentation/publication task. COST.md is the ledger.

## Next-session map and boundaries

- docs/answer-quality-status.md — consolidated architecture, scope, verified facts,
  limitations, configuration and migration boundary.
- CHANGE_INVENTORY.md — every changed path since ec0ef26 and its documentation owner.
- docs/modules/M4_conversational_planning.md — live debugging and corrections.
- docs/modules/M3_answer_quality_stage3.md — fixture evidence and real backfill needs.
- docs/testing/acceptance/ — immutable synthetic Stage 1/2/3 snapshots, not live proof.
- RESUME_NEXT_SESSION.md — short safe resume checklist.

Inspect backend/tests/conftest.py before tests. It creates/redirects to a `_test`
database; some suites DROP tables. Only the explicitly listed DB-free suites may
use `--noconftest`. Do not run DB-backed suites on the serving DB, regenerate frozen
baselines, index the corpus, change .env, spend on new live runs, deploy, or merge
without applicable authorization. Never print credentials or .env contents.
Temporary live services from this work were stopped. Restart the backend/refresh
frontend normally to load source changes; no serving process is managed here.


## Publication record

- `6befa4b` — `style: normalize existing backend formatting` (six AST-equivalent files).
- `770bcd0` — `fix: improve answer planning and evidence grounding` (connected runtime,
  tests, specs, module notes and frozen synthetic artifacts).
- The documentation commit containing this snapshot reconciles the remaining
  handoff/index/status files. Resolve it with `git log -1 -- context/CURRENT_TASK.md`;
  use Git refs/tracking state to confirm the latest publication rather than embedding
  this file's own commit hash.
- Target: `origin/plan/answer-quality-remediation`. Main is not merged or deployed.
- Final audit checks:177hermetic tests pass; whole backend Ruff/Black pass;
  frontend harness/build pass;237local Markdown links checked;123changed paths
  mapped to owners;6frozen snapshot hashes preserved. No new hosted/cloud spend.

Existing backend/.env may emit a parser warning around line44 while settings still
load. It was not edited and must not be printed or changed incidentally.
