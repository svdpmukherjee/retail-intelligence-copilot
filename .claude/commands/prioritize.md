---
description: Re-rank the backlog into an executable delivery plan — calls the Product Owner to turn BACKLOG.md into context/BACKLOG_PLAN.md (priority order, dependencies, parallel tracks, file-conflict map).
argument-hint: optional focus, e.g. "only the retrieval items" or "assume 2 parallel terminals"
---

Run the **Product Owner** (`.claude/agents/product-owner.md`) to produce or refresh
`context/BACKLOG_PLAN.md` from `context/BACKLOG.md`.

Steps:
1. Call the `product-owner` sub-agent, passing any focus the human gave in `$ARGUMENTS`.
2. It reads `BACKLOG.md` (+ `PRD.md`, `context/DECISIONS.md`), greps the codebase for
   each item's file domain, and writes the ranked plan + conflict matrix + wave plan to
   `context/BACKLOG_PLAN.md`.
3. Show the human the plan path and the **top wave** — what to start first and what can
   run in parallel. Stop. The human approves before any `/change` work begins.

This is a **planning** ritual: nothing is built. To act on an item, run
`/change <item>`. Re-run `/prioritize` whenever the backlog changes.
