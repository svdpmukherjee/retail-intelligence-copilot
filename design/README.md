# Design Track — experience design

This folder holds the copilot's **design-first iterations**, each produced by the
`designer` sub-agent and run via `/design`. It sits at the repo root (not under
`docs/`) because the design process is a first-class part of the work, not an
afterthought.

## Why this exists (honest framing)

v1 (modules M1–M8) was an **engineering spike**: it proved the agentic RAG
pipeline works end-to-end at $0, with a deliberately minimal UI. Only after that
did we add a proper design process on top — so this track is explicitly a
*later* iteration, not design-first. The ordering is dated in
`context/WORKLOG.md` and git history; we do not pretend design came first.

## Iterations

Each `/design` run writes a self-contained package into its own folder
`iteration-<N>/`. v1 was the engineering spike (no design package), so the
numbering starts at 2.

| Folder | Focus | Fed into |
|---|---|---|
| [`iteration-2/`](iteration-2/) | First design pass of the chat UI — role→render, evidence/trust surface, inspectable citations | M8 v2 rebuild |
| [`iteration-3/`](iteration-3/) | Conversation/memory layer — role+user identity, thread history (list/resume/new), stacked multi-turn with follow-ups, click-to-inspect evidence, declutter | M8 v3 rebuild |

Each iteration folder contains the same stages:

| File | Stage | What it is |
|---|---|---|
| `00_brief.md` | D1 | Objective, personas + jobs-to-be-done, current-UI gaps, UX success criteria |
| `01_wireframes.md` | — | Lo-fi annotated layouts for every state |
| `mockups/*.html` | D2 | Hi-fi, theme-aware, interactive mockup (the "Figma page"), derived from the brief |
| `02_decisions.md` | — | Design decision log + "deferred / where we stopped and why" |
| `03_handoff.md` | — | Build spec the Developer implements (components, states, data bindings, role→render, a11y) |

The mockup is derived from the brief and wireframes — not the other way round.
The artifact is the cheap part; the reasoning in `02_decisions.md` and the build
spec in `03_handoff.md` are the product. Cross-iteration deferred/visual work is
tracked in [`BACKLOG.md`](BACKLOG.md).

## Checkpoints

- **D1 — brief approval:** the problem framing is agreed before any pixels.
- **D2 — design approval:** the look + interaction are agreed before any build.

The human is the client; their approval at D1/D2 is the real sign-off. One
optional value/fit pass by the `solution-architect` checks the design serves the
personas and respects M6 access scope. No simulated PM/client personas.

## Handoff to build

Once an iteration's package is approved, `/module M8` is re-run as a **rebuild**,
using that iteration's `03_handoff.md` as a primary input — the normal plan →
build → test → document loop, producing the corresponding M8 frontend (and any
backend edge changes it needs).
