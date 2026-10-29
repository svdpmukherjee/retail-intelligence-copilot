# PROJECT.md — module status

Session-continuity file. The orchestrator reads this at session start and
updates it at session end. One row per module (see `PRD.md §10`).

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
