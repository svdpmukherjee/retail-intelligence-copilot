# Design Track — experience design (iteration 2)

This folder holds the **design-first pass** for the copilot's UI, produced by the
`designer` sub-agent and run via `/design`.

## Why this exists (honest framing)

v1 (modules M1–M8) was an **engineering spike**: it proved the agentic RAG
pipeline works end-to-end at $0, with a deliberately minimal UI. Reviewing that
UI showed it exposes almost none of the system's reasoning — it renders a plain
answer and throws away the rich `audit` record the backend returns.

So this is **SDLC iteration 2**: a proper design process layered on the working
system, then a frontend rebuild. The ordering is intentional and dated in
`context/WORKLOG.md` and git history — we do not pretend design came first.

## Contents (filled in as the track runs)

| File | Stage | What it is |
|---|---|---|
| `00_brief.md` | D1 | Objective, personas + jobs-to-be-done, v1 gaps, UX success criteria |
| `01_wireframes.md` | — | Lo-fi annotated layouts for every state |
| `mockups/*.html` | D2 | Hi-fi, theme-aware, interactive mockups (the "Figma page"), derived from the brief |
| `02_decisions.md` | — | Design decision log + "deferred / where we stopped and why" |
| `03_handoff.md` | — | Build spec the Developer implements (components, states, data bindings, role→render, a11y) |

The mockup is derived from the brief and wireframes — not the other way round.
The artifact is the cheap part; the reasoning in `02_decisions.md` and the build
spec in `03_handoff.md` are the product.

## Checkpoints

- **D1 — brief approval:** the problem framing is agreed before any pixels.
- **D2 — design approval:** the look + interaction are agreed before any build.

The human is the client; their approval at D1/D2 is the real sign-off. One
optional value/fit pass by the `solution-architect` checks the design serves the
personas and respects M6 access scope. No simulated PM/client personas.

## Handoff to build

Once the package is approved, `/module M8` is re-run as a **rebuild**, using
`03_handoff.md` as a primary input — the normal plan → build → test → document
loop, producing the M8 v2 frontend (and any backend edge changes it needs).
