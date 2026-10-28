---
description: Invoke the solution-architect for an independent business-value review at a milestone (a working, user-visible slice).
argument-hint: (optional) milestone name; else the latest completed slice
---

Call the `solution-architect` sub-agent for a business-value review of the work
completed so far: $ARGUMENTS

Give it `PRD.md`, `context/DECISIONS.md`, the relevant `docs/modules/*.md`, and
`COST.md`. Relay its review: business value, success metrics, cost vs value, open
questions, and verdict.

This is a **milestone gate**, not a per-module step — use it after a slice that
delivers user-visible value (e.g. once retrieval + chat work), not after plumbing
modules like Foundations or ETL. Nothing is changed by this review; if it
recommends changes, run `/change`.
