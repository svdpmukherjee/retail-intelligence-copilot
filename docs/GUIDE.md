# Project operating guide

How to pick up this repository, build it, see how it grows, change it safely, and
observe its cost and behaviour. Read this once; it points to everything else.

## 1. Read these first, in order
1. `README.md` — what the project is.
2. `PRD.md` — product & architecture backbone (start at §2 users, §10 modules).
3. `context/PROJECT.md` — module status: what's done, what's next.
4. `docs/repo-evolution.md` — visual tree of how the repo grew, per module.
5. `context/DECISIONS.md` — why things are the way they are (ADRs).

## 2. Mental model (how work happens)
- You talk to the **orchestrator** (Claude Code, driven by `CLAUDE.md`). It writes
  no feature code; it dispatches sub-agents and stops at your approvals.
- Build sub-agents: **planner** (writes a spec) → **developer** (builds) →
  **tester** (verifies) → **documenter** (writes the module note). They hand off
  via files, never directly.
- Review roles, outside the build loop: **solution-architect** (business-value
  review at milestones, via `/value-review`).
- Work is **one module per session**, each split into **sub-modules** built →
  verified → integrated one at a time. Two human gates: spec approval, module
  approval.

## 3. Run from scratch

Two **separate** activities — keep them apart:

- **Build / inspect the code** (module loop): clone, run `claude`, copy
  `backend/.env.example` → `backend/.env`, check `context/PROJECT.md` for the next
  TODO, then `/module <ID>` (or "build `<ID>`") and approve at both checkpoints.
  This runs against the committed **40-row sample** — $0, no data download.
- **Populate real data + run the live app** (one-off): follow
  **[`data-pipeline-setup/`](../data-pipeline-setup/README.md)** — `local/LOCAL_SETUP.md`
  for the $0 local stack, `cloud/CLOUD_SETUP.md` for the cost-gated Azure run. Those
  are the **single source of truth** for setup commands (download → medallion lake →
  embed → serve); they're not repeated here so they can't drift.

Free-tier mode (`PROVIDER_MODE=free`, the default) needs no Azure.

## 4. Understand how it grows
| Question | Look at |
|---|---|
| What's done / next? | `context/PROJECT.md` |
| What happened each session? | `context/WORKLOG.md` |
| What's in progress right now? | `context/CURRENT_TASK.md` |
| Why was something decided? | `context/DECISIONS.md` (ADRs) |
| What a module built + problems faced | `docs/modules/<ID>_*.md` |
| How the file tree changed, visually | `docs/repo-evolution.md` |
| What it has cost | `COST.md` |

## 5. Make a change safely
- **Think-first change:** `/change "<what you don't like>"` — the orchestrator (as
  architect) clarifies, offers options + a recommendation, you decide, it logs an
  ADR, edits only the relevant spec, and rebuilds only the affected sub-module.
- **Small obvious tweak:** just tell the orchestrator directly.
- **Business-value check:** `/value-review` calls the independent solution-architect
  at a milestone (after a user-visible slice, not after plumbing modules).
- **Who do you talk to?** Always the orchestrator. It routes to sub-agents; they
  never act on their own.

## 6. Observability (cost, time, quality)
| Signal | Where |
|---|---|
| Cloud spend ($) | `COST.md` (the budget that matters) + Azure budget alerts (Bicep) |
| Claude token usage | the `/cost` command in Claude Code |
| Build time per module | the "Build metadata" block in `docs/modules/<ID>_*.md` |
| Time per sub-agent | shown live in the terminal (e.g. `· 52s`) |
| Test results | the tester's report at CHECKPOINT 2; CI (`.github/workflows/ci.yml`) |
| Human acceptance tests (what we tried, found) | `docs/testing/uat.md` (method + capability matrix) + `docs/testing/uat-log.md` (dated log) |
| Answer quality / cost / latency | the evaluation gate (module M7) |
| Live agent dashboard (optional) | the Agents Observe plugin (`/observe`), if enabled |

## 7. Change management & modularity
`PRD.md` is the stable backbone — don't grow it for routine changes. Per-module
detail lives in `.claude/specs/`; decisions in `context/DECISIONS.md`. A new
feature = a new module row in `PRD.md §10` + a new spec. Changes stay localized
and the history stays auditable.

## 8. Glossary
- **RAG** — retrieval-augmented generation: fetch relevant text, ground the answer.
- **Medallion (bronze/silver/gold)** — staged data refinement in the ETL.
- **Bicep** — Azure infrastructure-as-code (cloud resources described as text).
- **ADR** — architecture decision record (one logged decision).
- **SIT / UAT** — system-integration / user-acceptance testing (see `docs/testing/`).
- **Provider mode** — the `azure` vs `free` backend switch (`PROVIDER_MODE`).
