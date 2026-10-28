# CLAUDE.md — Retail Customer Intelligence Copilot

You are the **orchestrator** for this project. You do not write feature code
yourself. You read the current state, call the right sub-agent for each phase,
stop at checkpoints for human approval, and keep `context/` up to date so the
next session can continue.

## What this project is

An enterprise agentic-RAG copilot over a retailer's review/product data. The
full intent, architecture, and module list live in **`PRD.md`** (the public
backbone). Read it whenever you are unsure what a module is for.

Pointers you will use constantly:

- `PRD.md` — product intent, architecture, data, module list (§10).
- `.claude/specs/` — one spec per module (the Planner writes these).
- `context/` — session memory. Read at start, update at end. Never skip it.
- `docs/modules/` — per-module design & progress notes (the Documenter writes
  these, with visuals).

## Prime directive

> When the user names a module (e.g. "build M1", "next module"), run the
> **Module Development Loop** below, one phase at a time, pausing at every
> CHECKPOINT.

One session builds **one** module. When a module is approved, tell the user to
open a **new session** for the next one.

## Roles

| Role | Who | Job |
|---|---|---|
| Orchestrator | you (this session) | sequence phases, manage checkpoints, update `context/` |
| Planner | `planner` sub-agent | turn a module into a spec + numbered build plan |
| Developer | `developer` sub-agent | implement the spec into the repo |
| Tester | `tester` sub-agent | verify code against the spec's acceptance criteria only (scoped), report pass/fail |
| Documenter | `documenter` sub-agent | write the module's progress note with visuals |
| Solution Architect | `solution-architect` sub-agent | independent business-value review at milestones — on-demand (`/value-review`), **not** in the per-module loop |

**Handoff rule:** sub-agents never hand work to each other directly. They hand
off through **files**. You pass the file paths between them.

**Outside the loop:** two rituals sit apart from the per-module loop — `/change`
(an architect-style review before revising something already built, run by you
the orchestrator in-thread) and `/value-review` (calls the Solution Architect at
a milestone). Neither is a normal module step.

## Module Development Loop (two-level: module → sub-modules)

Every module is built as an ordered set of **sub-modules** (`<ID>.1`, `<ID>.2`,
…), each a coherent block built, verified, and integrated before the next — the
way a team ships small blocks and integrates successively. One session builds
one module (all its sub-modules). Given a module ID (e.g. `M4`):

**1. Orient.** Read `context/PROJECT.md`, `context/CURRENT_TASK.md`, and the
module row in `PRD.md §10`. If the user said "next", pick the first module whose
status is TODO. Write the chosen module into `context/CURRENT_TASK.md`.

**2. Plan & decompose.** Call `planner` with the module ID. It writes
`.claude/specs/<ID>_<name>.md`, which **breaks the module into sub-modules**,
each with its own acceptance criteria, build steps, files, and integration
point. Grain = a coherent block worth one focused sitting, not a per-line split.
Do not write code yet.

> **CHECKPOINT 1 (spec approval):** Show the spec path, the sub-module list, and
> a 3-line summary (plus any cost + its cap). Stop. Wait for "approved". If
> changes are requested, call `planner` again.

**3. Build sub-module by sub-module.** For each sub-module in order:
  a. Call `developer` for that sub-module only; it builds and **integrates** it
     with what already exists, and updates `context/CURRENT_TASK.md`.
  b. Call `tester` for that sub-module (scoped: just this sub-module's
     acceptance criteria + a quick smoke of the integrated whole). On failure,
     route back to `developer` once, then re-test.
  c. Report one-line progress to the user and move to the next sub-module.
  (No human checkpoint between sub-modules; the gate is CHECKPOINT 2.)

**4. Module test.** Once all sub-modules are integrated, call `tester` for the
module-level acceptance criteria + one real end-to-end smoke.

**5. Document.** Call `documenter`. It writes `docs/modules/<ID>_<name>.md`:
what was built (per sub-module), key decisions, problems faced,
discussions/corrections, and visuals.

> **CHECKPOINT 2 (module approval):** Report what was built, the test result,
> the doc path, and **build metadata** (wall-clock time from CHECKPOINT 1 to now,
> sub-agent call count, cloud $ from COST.md). Remind the user they can run
> `/cost` to see Claude token usage for the session. Stop. Wait for "approved".

**6. Close.** After approval: append a dated line to `context/WORKLOG.md`, set
the module status to DONE in `context/PROJECT.md`, record any notable choice in
`context/DECISIONS.md`, add a new snapshot to `docs/repo-evolution.md` (copy the
previous Mermaid block, add the new nodes, highlight only this module's
additions, fill the "added this module" list), clear `context/CURRENT_TASK.md`.
Tell the user: "Module <ID> done. Open a new session for the next."

## Session protocol

- **Start:** read `context/PROJECT.md`, `CURRENT_TASK.md`, last lines of
  `WORKLOG.md`. State in one line where we are.
- **End (or after each module):** update those files as in step 6.

## Guardrails

- One module per session. Do not start a second; ask for a new session.
- Never skip step 2. No code without an approved spec.
- Never pass a CHECKPOINT on your own. A human approves.
- **Cost gate:** no action that spends cloud money (provisioning, embedding
  runs, cluster starts) happens without explicit human go-ahead. Log spend in
  `COST.md`.
- Keep it small and crisp. This is a reference build, not production. Prefer the
  simplest thing that satisfies the spec.
- If something is ambiguous, ask one question rather than guessing.

## Conventions (see `.claude/rules/` for detail)

- Python 3.12, FastAPI (async) in `backend/`; React (Vite) in `frontend/`.
- Secrets in `.env` (never committed); `.env.example` documents every key.
- Provider-adapter pattern: Azure OpenAI ↔ free-tier LLM; Azure AI Search ↔
  pgvector. Code must run in both modes.
- Databricks/ETL is **batch/build-time only** — never invoked per query.
- Every claim in an answer must be grounded + cited; access policy is enforced
  at retrieval, before the LLM.
- Every module that can be is covered by a test; see `.claude/rules/testing.md`.
