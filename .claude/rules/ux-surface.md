# UX surface — who the chat UI is for

- The chat UI serves a **non-technical retail user**. It answers their question in
  plain language with grounded, cited evidence — nothing more.
- **Internal operational data never appears in the user surface.** Metrics, internal
  ids, cost/tokens, routing decisions, latency, tool paths, model slugs, and any
  pipeline diagnostics are not shown to the retail user.
- That data has **two homes, both operator-facing, not the chat:**
  - the **audit plane** — `audit_log` (per-answer governance record: query, role,
    sources, tool path, tokens, cost, latency), surfaced only through the role-gated
    audit admin view.
  - the **observability plane** — Langfuse traces (span-level pipeline timings,
    tokens, cost), for operators debugging the system.
- When a build would expose an internal value in the chat (a metric chip, a routing
  label, a cost figure, a raw id), route it to the audit or observability plane
  instead. If it helps the retail user understand the *answer*, render it as plain,
  grounded, cited content — not as a system internal.
- This is a **surface-boundary rule, not a styling preference**: it keeps the user
  surface honest for a non-technical persona and keeps operator data where it is
  governed and auditable.
