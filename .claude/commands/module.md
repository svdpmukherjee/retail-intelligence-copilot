---
description: Run the full Module Development Loop for one module (plan → approve → build → test → document → approve → close).
argument-hint: <module-id, e.g. M3, or "next">
---

Run the **Module Development Loop** defined in `CLAUDE.md` for module: $ARGUMENTS

Follow it exactly, phase by phase:

1. **Orient** — read `context/` and the module row in `PRD.md §10`. If the
   argument is "next", pick the first TODO module in `context/PROJECT.md`.
2. **Plan & decompose** — call the `planner` sub-agent to write the spec,
   broken into ordered sub-modules, then STOP at CHECKPOINT 1 and wait for my
   approval (this is also the cost go-ahead if the module spends cloud money).
3. **Build sub-module by sub-module** — after I approve, for each sub-module in
   order: call `developer` to build + integrate it, then `tester` (scoped to
   that sub-module's criteria + a quick smoke); on failure route back to
   `developer` once, then re-test. Report one-line progress between sub-modules.
   No checkpoint between sub-modules.
4. **Module test** — once all sub-modules are integrated, call `tester` for the
   module-level criteria + one real end-to-end smoke.
5. **Document** — call the `documenter` sub-agent to write
   `docs/modules/<ID>_<name>.md`.
6. STOP at CHECKPOINT 2 and wait for my module approval.
7. **Close** — update `context/WORKLOG.md`, `context/PROJECT.md`,
   `context/DECISIONS.md`; clear `context/CURRENT_TASK.md`; remind me to open a
   new session for the next module.

Do not pass either checkpoint without my explicit approval. Build only this one
module in this session.
