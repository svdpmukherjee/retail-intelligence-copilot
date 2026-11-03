# AGENTS.md — Retail Customer Intelligence Copilot

> This repo was built with Claude Code, whose config lives in `CLAUDE.md` and
> `.claude/`. Codex does not auto-read those. This file bridges them: it inlines
> the always-on rules and points you at the rest. **`CLAUDE.md` remains the
> source of truth** — read it in full before any non-trivial work.

## Current-state handoff

Read `context/CURRENT_TASK.md` and `context/RESUME_NEXT_SESSION.md` before acting.
`docs/answer-quality-status.md` consolidates the post-`ec0ef26` remediation;
`context/CHANGE_INVENTORY.md` maps every changed path to its spec/note/tests.
Module DONE rows and older module/worklog notes describe historical baselines.
Later implementation, test, authorization and acceptance states may supersede them;
publication is not a quality acceptance or permission for migration/deployment.

## How to work in this repo (orchestration model)

You are an **orchestrator**, not a lone coder. The project is built **one module
per session**, through a phase loop with **human checkpoints** you must not pass
on your own. The full loop lives in `CLAUDE.md` ("Module Development Loop"); read
it before building a module. In short:

1. **Orient** — read `context/PROJECT.md`, `context/CURRENT_TASK.md`, and the
   module row in `PRD.md §10`.
2. **Plan** — produce a spec in `.claude/specs/<ID>_<name>.md` that breaks the
   module into sub-modules. **No code before an approved spec.** → CHECKPOINT 1.
3. **Build** sub-module by sub-module, testing each.
4. **Module test** — one real end-to-end smoke.
5. **Document** — `docs/modules/<ID>_<name>.md`.
6. → CHECKPOINT 2, then **close** (update `context/`, worklog, decisions).

**Checkpoints are human sign-offs — stop and wait for "approved". Never pass one
yourself.** One module per session; when it's done, tell the user to start a new
session.

## Roles / agents (Claude Code subagents → Codex can't spawn these)

Claude Code ran these as real subagents. Codex has no equivalent, so treat each
as a **role to adopt** when the task calls for it, and **read its full definition
file first** — the behavioral contract is in the file, not here:

| Role | Definition file | Job |
|---|---|---|
| Planner / Architect | `.claude/agents/planner.md` | module → spec + numbered build plan; writes one spec, no code |
| Developer | `.claude/agents/developer.md` | implement one approved spec; no scope beyond it |
| Tester / QA | `.claude/agents/tester.md` | verify against spec acceptance criteria; pass/fail |
| Documenter | `.claude/agents/documenter.md` | per-module progress note + visuals |
| Designer | `.claude/agents/designer.md` | design-first UI pass (brief → wireframe → mockup → handoff) |
| Product Owner | `.claude/agents/product-owner.md` | rank `BACKLOG.md` → `context/BACKLOG_PLAN.md` |
| Solution Architect | `.claude/agents/solution-architect.md` | independent business-value review at milestones |

**Handoff rule:** roles hand off through **files**, never directly. Pass file
paths between phases.

## Commands (Claude Code slash commands → now just prompts)

These were `/commands`. In Codex they are not real commands — read the file and
follow it as a prompt:

- `.claude/commands/module.md` — run the full Module Development Loop for a module.
- `.claude/commands/change.md` — architect-style review before changing built code (ADR + spec edit + rebuild affected sub-module).
- `.claude/commands/design.md` — run the Design Track for a UI surface.
- `.claude/commands/prioritize.md` — Product Owner re-ranks the backlog.
- `.claude/commands/value-review.md` — Solution Architect business-value review.

## Specs

One spec per module in `.claude/specs/` (M1–M8, B13 observability, B14 audit/admin).
Read the relevant spec before building or changing that module.

## Always-on rules (inlined — full detail in `.claude/rules/`)

**Architecture & conventions** (`CLAUDE.md`, `.claude/rules/code_style.md`):
- Python 3.12, FastAPI (async) in `backend/`; React (Vite) in `frontend/`.
- `ruff` + `black`; type hints on public functions; prefer `async def` for I/O.
- Config via environment (`.env` + `pydantic-settings`); **never hard-code** URLs,
  keys, model slugs, or paths. Every key documented in `.env.example`.
- Provider-adapter pattern: Azure OpenAI ↔ free-tier LLM; Azure AI Search ↔
  pgvector. **Code must run in both modes.**
- Databricks/ETL is **batch/build-time only** — never invoked per query.
- Errors fail **loud but clean**: typed `HTTPException` + JSON `detail`, never an
  unhandled 500. Frontend wraps API calls in try/catch, never a silent blank state.

**Security & responsible AI** (`.claude/rules/security.md`):
- Secrets only via `.env` (gitignored) / secret store. Never commit, log, or print.
- **Access control enforced at retrieval, before the LLM** — not by asking the
  model to behave. A user must not retrieve evidence outside their scope.
- Redact PII at ingestion; commit only the redacted/derived index.
- Every generated claim maps to retrieved evidence and is **cited**; block uncited claims.
- Every answer logs query, role, sources, tool path, tokens, cost, latency.

**Testing** (`.claude/rules/testing.md`):
- `pytest`. At least **one real end-to-end check per data/LLM path**, not only mocks.
- Retrieval/answer quality has an **evaluation gate** (recall@k/MRR, faithfulness,
  cost/query, p50/p95) that fails the build on regression.
- A live check that can't run (missing key/quota) is **reported plainly, not a silent PASS**.
- Tests index a **small bounded slice**, never the full corpus; expensive read-only
  corpus built once per session; mutable tables truncated per test; route to
  `<db>_test` via `conftest.py`.

**UX surface** (`.claude/rules/ux-surface.md`):
- Chat UI serves a **non-technical retail user**: plain-language, grounded, cited answers.
- **Internal operational data never appears in the chat** (metrics, ids, cost/tokens,
  routing, latency, model slugs). It belongs to the **audit plane** (`audit_log`,
  role-gated admin view) and **observability plane** (Langfuse) only.
- Honest fallback states stay visible but worded for a non-technical reader — never
  pipeline tokens like `extractive`, `sql_rag`, `llm draft blocked`.
- Identity switcher is **demo-only**; mark it as a demo control, not product chrome.

## Guardrails

- One module per session. Don't start a second — ask for a new session.
- No code without an approved spec. Never pass a checkpoint on your own.
- **Cost gate:** nothing that spends cloud money (provisioning, embedding runs,
  cluster starts) without explicit human go-ahead. Log spend in `COST.md`.
- Keep it small and crisp — a reference build, not production. Simplest thing that
  satisfies the spec.
- If something is ambiguous, ask one question rather than guessing.

## Session memory

`context/` is session memory: read `PROJECT.md`, `CURRENT_TASK.md`, and the last
lines of `WORKLOG.md` at the start; update them at the end. Never skip it.
