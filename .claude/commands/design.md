---
description: Run the Design Track — a design-first iteration (brief → wireframe → hi-fi mockup → decisions + handoff) for a UI surface, feeding a frontend rebuild.
argument-hint: (optional) surface to design; default is the M8 chat UI
---

Run the **Design Track** defined in `CLAUDE.md` for the surface: $ARGUMENTS
(default: the M8 chat/serving UI).

This is a **design-first iteration**, run apart from the per-module loop. It
produces a design package, then feeds a normal `/module M8` rebuild. Frame it
honestly (v1 was an engineering spike; the first design pass is iteration-2),
never as design-first.

**Each run writes its package into its own iteration folder `design/iteration-<N>/`**
(iteration-2 = the first design pass; iteration-3 = the conversation-UI pass; the
next is iteration-4, and so on). Pick the next unused `<N>`; the cross-iteration
index is `design/README.md`.

Phase by phase, pausing at the design checkpoints:

1. **Brief.** Call the `designer` sub-agent to write `design/iteration-<N>/00_brief.md`
   (objective, personas + jobs-to-be-done, what the current UI fails to show, UX
   success criteria). STOP at **CHECKPOINT D1** — I approve the problem framing
   before any pixels.
2. **Wireframe.** After I approve, call `designer` for `design/iteration-<N>/01_wireframes.md`
   (lo-fi, all states). One-line progress to me.
3. **Hi-fi mockup.** Call `designer` to build `design/iteration-<N>/mockups/<surface>.html`.
   Publish it as an artifact so I can click it. STOP at **CHECKPOINT D2** — I
   approve the look + interaction.
4. **Decisions + handoff.** After I approve, call `designer` for
   `design/iteration-<N>/02_decisions.md` (incl. "deferred / where we stopped and why")
   and `design/iteration-<N>/03_handoff.md` (component inventory, states, data
   bindings to `POST /query` + `audit`, role→render rules, a11y).
5. **Value/fit review (optional).** If I ask, call `solution-architect` on the
   design: does it serve the PRD §2 personas, and does every view respect M6
   access scope?
6. **Hand off to build.** When I say so, run `/module M8` (a rebuild) with that
   iteration's `03_handoff.md` as a primary input to the planner, then build /
   test / document the frontend+backend.

Do not pass D1 or D2 without my explicit approval. The designer never writes
application code; the Developer builds from the handoff.
