# CURRENT_TASK.md

No module in progress.

**M8 v2 — Serving & UI (design-driven rebuild) is DONE** (closed 2026-10-28). SDLC
iteration 2: a design-first redo of the M8 chat UI on the unchanged backend, fed by the
Design Track package. Built in 5 sub-modules, all first-pass, zero build-backs. Two
additive backend edges (redacted `citations[].snippet`; `audit.scope`), full state
machine, 3 role shapes, trust strip, docked Evidence panel, a11y contract. Module gate
PASS incl. live e2e (free mode, $0). All three `/change` ADR conditions met (marketing
scope, snippet redaction, no hard-coded chips). Spec `.claude/specs/M8v2_serving_ui.md`;
note `docs/modules/M8v2_serving_ui.md`. The Design Track is now DONE in `PROJECT.md`.

**Known limitation (logged in `DECISIONS.md` + the M8v2 note):** the UI is functionally
correct but does NOT match the D2-approved mockup's visual design (`App.css` ~109 lines
vs mockup ~1157; design tokens/typography/spacing/card-chat-evidence-chart styling not
ported; no browser visual-QA ran). The handoff carried behaviour, not the visual spec.
**Fix = a scoped `/change`** (port the mockup's tokens/styling into `App.css` + add a
browser visual-QA step), NOT a reopen of this module.

**Open items (human):**
- Run the scoped `/change` for visual fidelity (above).
- Capture per-persona UI screenshots (support/marketing/executive) under `docs/img/` and
  link them in the M8v2 note.
- Theme contrast + phone-width no-horizontal-scroll verified by code only — confirm in a
  browser during the visual `/change`.

**Remaining module:** M9 (Documentation — consolidated architecture diagrams + design
record), the last TODO in `PROJECT.md`. Open a new session to run `/module M9`.
