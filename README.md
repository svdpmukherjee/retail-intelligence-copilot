# Retail Customer Intelligence Copilot

An enterprise **agentic-RAG** assistant that lets retail staff query a company's
own customer, product and review data in natural language — returning grounded,
cited, access-controlled answers. A router agent chooses the right retrieval
strategy per question (structured analytics vs. semantic search), and a composer
merges the evidence into one cited answer.

See **[`PRD.md`](./PRD.md)** for the full product and architecture spec.

## How this repo is built

The project is built incrementally, one module at a time, by an **orchestrated
agent system** (the same way a small engineering team works: plan → build → test
→ document → review). This makes the build reproducible — anyone can clone the
repo and continue from the recorded state.

```
Human (reviewer) ── triggers one module ──▶ Orchestrator (CLAUDE.md)
                                              │ plan / build / test / document
                                              ▼
                        planner → developer → tester → documenter  (sub-agents)
                                              │ hand off via files
                                              ▼
                   code + tests + docs/modules/<ID>.md  ──▶ human approval
```

- **`CLAUDE.md`** — orchestrator instructions + the Module Development Loop.
- **`.claude/agents/`** — the four sub-agent roles.
- **`.claude/specs/`** — one spec per module (written before any code).
- **`.claude/rules/`** — code style, security, testing standards.
- **`context/`** — session memory (status, current task, worklog, decisions).
- **`docs/modules/`** — per-module progress notes with decisions and visuals.

## Reproduce from scratch

1. Clone the repo; install [Claude Code](https://docs.claude.com/en/docs/claude-code).
2. Read `PRD.md` (what we're building) and `context/PROJECT.md` (where we are).
3. In a new session, say **"build M1"** (or "next"). The orchestrator runs the
   loop and stops for your approval at each checkpoint.
4. Prerequisites for cloud modules (M2+): an Azure subscription; keys go in
   `backend/.env` (template in `.env.example`). Cloud spend is gated — see
   `COST.md`. A free-tier mode runs the whole thing without Azure.

## Status

Module progress is tracked in [`context/PROJECT.md`](./context/PROJECT.md).

**New here?** Read **[`docs/GUIDE.md`](./docs/GUIDE.md)** — the operating guide for
running, growing, changing, and observing the project.
