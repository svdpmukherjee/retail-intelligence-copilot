# PROJECT.md — module status

Session-continuity file. Read this with CURRENT_TASK.md and RESUME_NEXT_SESSION.md.
The table records the original module baseline, not acceptance of later answer-quality
remediation. Current details: [consolidated status](../docs/answer-quality-status.md).

| ID | Module | Status |
|----|--------|--------|
| M1 | Foundations (repo, IaC skeleton, config, budget alerts, cost tracking) | DONE |
| M2 | Data ingestion & ETL (Databricks medallion → Delta + Blob) | DONE |
| M3 | Indexing (embed review subset → vector store; parse docs → index) | DONE |
| M4 | Retrieval & agents (router + SQL/review-RAG/docs-RAG + composer) | DONE |
| M5 | Conversation & memory (threads, short/long-term memory, memory manager) | DONE |
| M6 | Governance (access policy, PII redaction, citations, audit log) | DONE |
| M7 | Evaluation (metrics harness + CI gate) | DONE |
| M8 | Serving & UI (FastAPI + React, deploy to Azure) | DONE |
| M9 | Documentation (architecture diagrams + consolidated design record) | TODO |

Status values: TODO → IN PROGRESS → DONE.

**Design Track (v2, design-first iteration):** apart from the module loop. Run via
`/design`; produces a design package in `design/`, then feeds an M8 rebuild.
Status: **DONE** (2026-10-28). Framed honestly as iteration 2 (v1 = engineering spike).
The design package (`00_brief`→`03_handoff` + `mockups/m8-chat.html`, approved D2) fed
the **M8 v2 rebuild** — behaviourally complete and verified live at $0 (spec
`.claude/specs/M8v2_serving_ui.md`, note `docs/modules/M8v2_serving_ui.md`).
The visual-fidelity follow-up (port design tokens/styling + browser visual-QA) was then closed
via a scoped `/change` (2026-10-29), logged in `DECISIONS.md`.

**Design Track iteration 3 (M8 v3) — DONE (2026-10-29).** The conversation/memory layer the
v1/v2 spikes deferred: demo identity switcher (owner selector, not auth), owner-scoped history
rail + phone drawer, stacked multi-turn with honest-degrade resume (D-21), one-at-a-time
Evidence. One read-only backend edge (`GET /threads` + `GET /threads/{id}` +
`MemoryStore.list_threads`/`get_thread`, no schema DDL change) on the **unchanged pipeline**.
Built from `design/iteration-3/03_handoff.md` in 5 sub-modules; module gate PASS incl. live e2e
and a live browser visual-QA gate (free mode, $0). Spec `.claude/specs/M8v3_serving_ui.md`; note
`docs/modules/M8v3_serving_ui.md`. Open items (human): phone layout reflow spot-check on a real
device (env viewport floor ~1353px), 4 error-state banners not force-driven, and the pending
per-turn audit/citations persistence (§2 option c) for full-fidelity resume.

**Design Track iteration 4 (M8 v4 baseline) — DONE (2026-11-02).** User-centred declutter + trust redesign of
the M8 chat surface for a non-technical retail user, on the **unchanged** pipeline, plus **exactly one**
additive backend field (`citations[].display_label`, D-30 — readable source-chip label derived server-side
by source type, PII-safe). Removed all operator instrumentation (SessionCard/TrustStrip/ScopeCard/ScopeRibbon)
to the audit + Langfuse planes; re-worded honest states as plain reassurance; `answering as: <role>` header;
derived plain scope line; demo switcher set apart; bounded scrollable history rail. Built from
`design/iteration-4/03_handoff.md` + the approved D2 mockup in 5 sub-modules (0 build-backs); module gate PASS
incl. live e2e (free mode, $0) + forbidden-surface count 0 + governance intact. Two UAT fixes applied in review
(bounded history scroll; "Your Chat History" rename). Spec `.claude/specs/M8v4_serving_ui.md`; note
`docs/modules/M8v4_serving_ui.md`. Open items (human): review `display_label` always category form (no
product-title field in `Chunk`); inherited `HISTORICAL_NOTE` wording; no browser visual-QA this pass +
per-persona screenshots; restored-turn per-turn citations persistence (handoff §3.1).

## Current answer-quality remediation (2026-11-03)

| Scope | Implementation / acceptance |
|---|---|
| Stage 1 before-baseline | Accepted; frozen synthetic artifacts retain observed failures |
| Stage 2 routing/SQL/access | Bounded implementation accepted; not an overall quality pass |
| Stage 3 evidence foundations | Built + isolated fixture verification; review pending; no serving backfill/cutover |
| Practical Stage 4 workaround | Source-first selected-product evidence and presentation fixes built; review pending |
| Conversational repair | Schema-informed planning, saved criteria, product-grain prices, compound tasks and suggestions built; review pending |
| Stage 5 tuning / model bake-offs | Not started |
| Documentation/publication | Audit complete; formatting/implementation/handoff commits on feature branch; see CURRENT_TASK.md and Git refs |

Current implementation and safety/verification limits:
[docs/answer-quality-status.md](../docs/answer-quality-status.md).
Every changed path is mapped in [CHANGE_INVENTORY.md](CHANGE_INVENTORY.md).
The worklog and original module notes retain dated intermediate results; later
status here and CURRENT_TASK.md supersedes old “unstarted/uncommitted/unmeasured”
statements. Publishing does not imply quality acceptance, main merge or deployment.
