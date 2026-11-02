# 02 · Design Decision Log — M8 Chat / Serving UI · **iteration 4**

**Design Track · iteration 4 · Stage 4 (decision log).** Written after the hi-fi
mockup (`i4/mockups/m8-chat.html`) was approved at CHECKPOINT D2 (with one label
change applied — see D-27). This is a **delta** on the iteration-2 and iteration-3
logs: **D-01 … D-21 carry forward unchanged by reference** (trust/governance
model, three role shapes, state machine, theme tokens, the conversation shell,
one-at-a-time evidence, scope/snippet binding to real fields). Iteration 4
continues the series at **D-22** and records only what it adds, changes, or
*removes*.

> **Honest framing — a declutter, not a rewrite.** v1 (M1–M8) was an engineering
> spike built first (dated in git / `WORKLOG.md`); design came after. Iteration 2
> made a single answer trustworthy; iteration 3 added the conversation/memory
> layer. **Iteration 4 is the third design pass: a user-centred declutter + trust
> redesign** that makes the surface honest for a non-technical retail persona. It
> changes **no** pipeline, retrieval, or governance behaviour — only what the chat
> surface shows and how it is worded. The governing rule is
> `.claude/rules/ux-surface.md` (updated 2026-11-02), which names the iteration-3
> build as the violation this pass fixes.

---

## 1. Decision log (iteration-4 additions)

### 1.1 The declutter — operator values leave the chat (G1–G4)

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-22** | **Remove the whole SESSION panel** (Cost, Tokens, Latency, Thread id, User id, Provider). | Keep it, minimised or collapsed. | Pure operator instrumentation with no meaning to a retail user; already governed and visible in the **audit plane** (`audit_log` via the role-gated audit admin view) and the **observability plane** (Langfuse traces). ux-surface worked-example item 1. A "minimised" panel still trains the user to read metrics — the surface boundary is binary, not a slider. |
| **D-23** | **Remove every per-answer footer chip** — the route/intent pill, the `grounded (extractive/llm/none)` pill, the latency pill, the cost pill, the `why ▾` expander, and the `⚠ fallback: <issue>` note. A clean grounded answer now carries **no badge at all**. | Keep a single "grounded" badge as reassurance. | The chips are pipeline diagnostics (G2); even a lone "grounded" badge is a system label that a non-technical reader must decode, and it invites the question "when is it *not* grounded?" Trust is carried instead by **readable source chips** (D-25) — the evidence itself, not a status token. Reasoning/timing still exist for operators in the audit + observability planes. |
| **D-24** | **Brand line = "grounded · cited"** (drop `$0/query`); **conversation header = "answering as: &lt;role&gt;"** (drop the `· <intent>` routing half). | Keep `$0/query` as a selling point; keep `role · intent` for "transparency". | `$0/query` is a cost brag — an operational figure dressed as a feature (G3). The `intent` half (`sql_rag`, `review_rag`, …) is an internal routing label (G4). Neither helps the retail user; both leak internals. The role half, re-worded as "answering as: support", is genuine reassurance (D-26). |

### 1.2 Honest states re-worded as reassurance (G5)

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-25a** | **Re-author every honest/fallback state into plain reassurance, selected from field presence, never rendered as a system token.** Verbatim/extractive → lead **"Here are the exact words from the sources:"** + the quoted evidence (calm, accent-bordered, *not* a warning). SQL/compute failure → lead **"We couldn't calculate the numbers for this one — here's what customers actually said:"** + the review-grounded remainder. Nothing-found → **"I couldn't find anything about that in the sources you have access to."** + a recovery suggestion. | Keep the current `copy.ts` strings ("The data query failed, so metrics and trends are hidden…", "Shown as a verbatim extract because the written answer could not be fully verified"); surface raw grounding tokens. | The grounding/fallback behaviour is the product's whole point and MUST stay visible — but the old copy reads as an error dump to a non-technical reader (G5, ux-surface "Honest messages must speak the user's language"). Re-worded, the *departure* becomes a mark of honesty ("here's exactly what the sources say"), which is what a support agent actually wants. No forbidden token (`extractive`, `llm draft blocked`, `sql_rag`, "query failed") ever reaches the surface. |
| **D-25b** | **A clean grounded answer gets NO note.** Only a *departure* from the ideal (extractive fallback, SQL failure, no evidence) adds a short plain line. | Always show a reassurance line ("fully verified ✓") on good answers. | A constant "verified" banner is noise that dilutes the signal of the real departures, and it re-introduces a status chip by the back door (D-23). Silence *is* the good state; the source chips already prove grounding. |

### 1.3 Evidence as human-readable source chips (G6)

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-26** | **Citations render as human-readable source chips** — `Source: return-refund policy` — not raw `source_id`/`[n]` markers. The chip text binds to the new `display_label` field (D-30). Clicking a chip reveals **exactly one** source at a time: its readable title + the already-PII-redacted snippet (redaction tokens like `[EMAIL]`/`[PHONE]` shown verbatim), in the **right dock on desktop** / a **bottom sheet on phone**. Clicking a different chip **replaces** it. A `null` snippet → a plain "the exact words aren't available to show", never fabricated text. | Keep inline `[n]` markers + raw `source_id` in the evidence item (iteration-3). Dump all sources of a turn at once. | A retail user can't read `B07PXV3V7X#2`; a citation shouldn't need decoding (G6). A readable label *is* the trust signal. One-at-a-time (inherited D-19) keeps the inspection precise and the dock bounded across a long thread. The UI never un-redacts or re-derives — it shows the server-redacted snippet verbatim (inherited D-20). |

### 1.4 Reassurance, scope, and the demo control

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-26b** | **"answering as: &lt;role&gt;" reassurance line** in the conversation header (role only) + a **plain scope line** in the empty state, both **derived from `audit.scope`** ("You can see Electronics, Home & Kitchen, Automotive and Pet Supplies" / "You can see all product categories"). | A technical scope card with `restricted: true`, raw category slugs, and a "retrieval filtered" flag (iteration-3 ScopeCard). | Scope should read as quiet reassurance in the user's language (ux-surface "Demo scaffolding… phrase access in user terms"), never as a governance mechanism (G4). It stays a **read-only derived fact** — the UI never widens or hard-codes it (inherited D-07/D-20). |
| **D-27** | **Demo switcher set apart as demo-only, with the approved label convention `user_id (<team> team)`** — the options read **"support_1 (support team)", "support_2 (support team)", "marketing_1 (marketing team)", "executive_1 (executive team)"** (user_id followed by "(&lt;team&gt; team)", NOT "user_id — role"). Dashed warning border, "⚙ demo — not a login" tag, a note that it is not part of what a retail user uses. | Style it as a normal account/identity control (iteration-3); label options "user_id — role". | The switcher exists only to make owner-scoping observable to a reviewer; styled as product chrome it misrepresents a demo affordance as auth (G7, ux-surface "Demo scaffolding is not product"). The approved `(<team> team)` wording reads in plain human terms rather than exposing "role" as a system field. Real auth stays deferred (inherited D-16). |

### 1.5 Layout & guidance

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-28** | **Bounded, fixed-height, auto-scrolled transcript** — the stream is a fixed-height region that scrolls internally, newest turn at the bottom, auto-scrolled on each new answer; the composer stays pinned; the page itself never grows unbounded. Older turns via scroll + the History rail. | An infinitely growing page (append-and-grow). | ux-surface "Layout: a bounded, scrollable transcript". A growing page loses the composer, breaks the ChatGPT-level mental model, and degrades at phone width. (Reaffirms the iteration-3 stacked-turn container's scroll contract, now an explicit requirement.) |
| **D-29** | **Suggested starters (empty state) + suggested follow-ups (under each answer)**, role-appropriate, as plain clickable prompts. | No guidance; rely on the user to phrase queries. | JTBD-3: the lead persona often doesn't know the "right" wording. Starters/follow-ups lower the cost of a good question and make the vague-follow-up path (the carry-forward acceptance criterion) a one-click demo. Follow-ups are presentation only — they post ordinary queries through the unchanged pipeline. |

### 1.6 The source-chip label field (resolves the i4 open question)

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-30** | **Add a new backend field `display_label: str` to the `Citation` model and the `POST /query` `citations[]` contract — a human-readable label for the UI source chip, kept DISTINCT from the existing `label`.** `label` stays **unchanged** (still used by the extractive answer text and the LLM prompt); the chat chip binds to `display_label` only. The composer derives it **by source type**: *review* → drop the raw ASIN, use `"customer review · <Category>"` (underscores→spaces, title-cased) or the product title if available; *doc* → a prettified human title (not the slug/filename), optionally `"<Title> · <Section>"`; *SQL* → `"Calculated from your data"`. | **(a) Reuse `label` as the chip text** — it carries raw ids/ASINs/slugs that would leak onto the surface (fails G6), and re-wording it in place would change the answer text and LLM prompt that depend on it (regression). **(b) Prettify `label` client-side** in the frontend — brittle string-munging of ids, duplicated across any consumer, and still parses raw ids in the browser. | The human picked Option B. A dedicated server-derived field gives a clean, readable chip without ever shipping an ASIN/slug/raw id to the surface, while `label` is preserved so answer composition and the prompt are untouched (no regression). **PII-safe by construction:** `display_label` is derived from category / product title / document title only — **no raw user/review text** flows into it — so it is safe to render unredacted. (The redacted `snippet` remains the only verbatim source text, already PII-redacted at source — inherited D-20.) This is the **only** new field in iteration 4; everything else binds to the already-shipped contract. |

---

## 2. Deferred / where we stopped and why

Conscious stops for a reference build. **Iteration-2 and iteration-3 deferred
items hold by reference.** New/updated status below.

| Deferred item | Inherited or new | Why stopped here | What a later pass would add |
|---|---|---|---|
| **Real authentication / server-asserted identity.** | Inherited (D-16). | The switcher is a *demo* owner selector (D-27), now with `(<team> team)` labels; still no login, no session trust boundary. | Role asserted by an identity provider; `user_id` as an authenticated principal; `GET /threads` authorising the caller. BACKLOG "Real auth". |
| **Thread rename / search / delete.** | Inherited (D-17). | History is list + reopen + new only; management verbs prove nothing about the governed pipeline. | Rename, search/filter, delete-with-confirm, pin/archive. BACKLOG "History search / rename / delete". |
| **Streaming answers.** | Inherited (D-12, PRD §5 non-goal). | Out of scope; the "Looking through the sources…" beat stands in for progress. | Token streaming with an `aria-live` transport. |
| **Full-fidelity resume of audit + citations on old turns.** | Inherited (D-21). | `messages` persists redacted text only; audit/citations aren't stored. Restored turns show stored text. **Iteration 4 does NOT close this** — and in fact it reduces the gap's visible impact: since the surface no longer shows a trust strip, a restored turn's missing audit is far less noticeable; it just lacks clickable source chips. | Persist per-turn `audit` + `citations` so restored turns get the same source chips as live ones (§2 of i3 handoff). Still a schema add, out of scope here. |
| **Restored-turn evidence in the mockup shown as live.** | Inherited (D-21). | The i4 mockup renders source chips on reopened threads as a flagged canned convenience; the build must degrade honestly (restored turns have no stored citations until the persist change lands). | Same as above. |
| **Phone reflow real-device spot-check.** | **Inherited from iteration-3's open items — still open.** | The mockup is responsive (bottom-sheet evidence, history drawer, 16px gutters, no h-scroll) and was reviewed in-browser, but not spot-checked on a physical phone. | A quick real-device pass (iOS Safari + Android Chrome) at build time; verify the sheet/drawer focus + Escape behaviour on touch. |
| **A "verified ✓" affirmation on good answers.** | **New (closed).** | Rejected per D-25b — a constant banner is noise and a status chip by the back door. | If user testing shows the silence is unsettling, revisit a single subtle grounding affordance — but only after evidence. |
| **Analytics beyond a single legible bar/trend.** | New. | The SQL/compute-failure state shows a simple themes bar to prove analytics stays legible and scoped; richer charts (the iteration-2 role shapes) remain available but weren't re-designed this pass. | Re-skin the executive ranked-bars / trend shapes to the decluttered language if an analytics-heavy persona is prioritised. All still fed by the same M6-scoped retrieval — design must not outrun governance. |

---

*Paired with: `03_handoff.md` (the build spec for the M8 v4 redesign). Sources:
`i4/00_brief.md`, `i4/01_wireframes.md`, `i4/mockups/m8-chat.html` (approved D2);
inherited logs `design/iteration-2/02_decisions.md` (D-01…D-15) and
`design/iteration-3/02_decisions.md` (D-16…D-21); the real contract in
`frontend/src/api/types.ts`, `backend/app/main.py`, `agents/pipeline.py`,
`agents/composer.py`; and the governing rule `.claude/rules/ux-surface.md`.*
