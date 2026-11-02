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

## Honest messages must speak the user's language

The grounding/fallback behaviour is a feature and MUST stay visible — but worded for
a non-technical reader, never in system terms.

- Never surface pipeline tokens in the UI: `extractive`, `llm draft blocked`,
  `sql_rag`, `grounded (llm)`, `query failed`, `not filtered`, `no session trust`.
- Re-author each honest state as plain reassurance, e.g.:
  - verbatim fallback → "Here are the exact words from the sources" (not "verbatim
    extract because the written answer could not be fully verified").
  - SQL/compute failure → "We couldn't calculate the numbers for this one — here's
    what customers actually said" (not "The data query failed, so metrics … hidden").
- A cited, grounded answer needs no warning at all. Only *departures* from the ideal
  (showing raw evidence instead of a synthesised answer) get a short, plain note.

## Demo scaffolding is not product

- The identity switcher is **demo-only** (it exists to show owner-scoping). Visually
  mark it as a demo control, separate from the product chrome — never styled as a
  feature the retail user "uses".
- Phrase access/scope in user terms: "You can see all categories" — not "Retrieval is
  not filtered for this role" or "no session trust".

## Layout: a bounded, scrollable transcript

- The conversation lives in a **fixed-height, scrollable region**, newest message at
  the bottom, auto-scrolled on each new answer — never an infinitely growing page.
- Older turns are reached by scrolling within that region and via the History sidebar.

## Worked example — the iteration-3 build violates this rule

Concrete inventory to remove/relocate (checkable against the live UI, 2026-11-02):

- **Remove the whole SESSION panel** (Cost, Tokens, Latency, Thread id, User id,
  Provider) → it already lives in the audit view and Langfuse.
- **Remove per-answer footer chips**: tool/routing tag, `grounded (extractive)`,
  latency, cost, the `why ▾` expander, `fallback: llm draft blocked`.
- **Header tagline**: drop `$0/query`; keep a plain product line (e.g. "grounded · cited").
- **Conversation header**: drop the `· <intent>` half (`executive · sql_rag` → role/scope only).
- **Per answer, the user sees only**: the answer in plain language, citations as
  human-readable **source chips**, and — where it builds trust — a short scope line.
  Nothing else.
