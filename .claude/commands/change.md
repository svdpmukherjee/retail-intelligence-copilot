---
description: Run an architect-style change review before touching code — clarify, weigh options, decide, log an ADR, edit the relevant spec, then rebuild only the affected sub-module.
argument-hint: what you want to change, e.g. "the composer's citation format"
---

# Change review: $ARGUMENTS

Use this when something already built isn't right and you want to think before
editing. I (the orchestrator) act as the **system/software architect** — I hold
the full project context, so we spar here in the main thread; no separate agent.

Run these steps, pausing where noted:

1. **Clarify.** Restate the problem in one line. Identify which module and which
   `.claude/specs/<M>.md` / files it touches. Ask one question only if truly blocked.
2. **Options.** Present 2–3 options as a short table with trade-offs (effort, risk,
   cost, impact on other modules) and a recommendation.
3. **Decide.** STOP. Wait for the user to pick, or spar further until they approve.
4. **Record.** Append an ADR to `context/DECISIONS.md` (decision → why → rejected
   alternative).
5. **Localize.** Edit only the affected `.claude/specs/<M>.md` (not `PRD.md`, unless
   the product direction itself changed).
6. **Rebuild.** Re-run just the affected sub-module(s) through the Module
   Development Loop (developer → scoped tester → update the module's doc note). Do
   not rebuild unrelated modules.

For a tiny, obvious tweak, the user may skip this ritual and just ask directly —
this is for changes worth thinking about.
