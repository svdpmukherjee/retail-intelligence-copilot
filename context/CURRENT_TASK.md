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

**Visual-fidelity `/change` — DONE (closed 2026-10-29).** The known visual gap is resolved.
Approach A (ADR 2026-10-29): ported the D2 mockup stylesheet as the visual contract into
`frontend/src/App.css` (109 → ~417 lines, full light/dark tokens + type/spacing/shadows) and
re-marked every shell/rail/panel/shape/trust/evidence/state component to the mockup's DOM —
restyle only, behaviour/data-bindings/state-machine/governance held invariant. Fixed a
session-card overflow (long `thread_id`/`user_id` spilling onto the chat). New gate **browser
visual-QA** run live (desktop + phone, light + dark) across all structurally distinct surfaces
— all match the mockup; governance verified live (scope chips only from `audit.scope`, snippets
redacted, scope read-only). `npm run build` green, category grep clean, $0. Details in the
M8v2 note + `DECISIONS.md`.

**Open items (human):**
- Capture per-persona UI screenshots (support/marketing/executive) under `docs/img/` and
  link them in the M8v2 note (optional polish; QA was driven live this session).
- 4 edge states (`400` / `502` / `no-evidence` / `degraded-SQL`) were not driven live
  (banner/calm-block variants; CSS ported). Force them if a future change touches them.

**Remaining module:** M9 (Documentation — consolidated architecture diagrams + design
record), the last TODO in `PROJECT.md`. Open a new session to run `/module M9`.
