# 00 · Design Brief — M8 Chat / Serving UI · **iteration 4**

**Design Track · iteration 4 · Stage D1 (brief).** Stops at CHECKPOINT D1 for
human approval. No wireframes, mockups, decisions, handoff, or application code
yet — this document fixes the *problem framing* for iteration 4 only.

> **Honest framing — design came after the spike, and this is the third design
> pass.** v1 (modules M1–M8) was an **engineering spike**, built first to prove
> the agentic-RAG pipeline works at ~$0. Git history and `context/WORKLOG.md` are
> dated — design did **not** come first. The design track started *after* the
> spike shipped: **iteration-2** was the first design pass (make a single answer
> trustworthy); **iteration-3** was the second (the conversation / memory layer —
> identity, history rail, stacked turns). **Iteration-4 is the third design pass:
> a user-centred declutter + trust redesign** that makes the surface honest for a
> non-technical retail persona. (Folder numbers are offset by one from the design
> pass count because `iteration-1` is the v1 spike's conceptual slot.) It changes
> **no** pipeline, retrieval, or governance behaviour — only what the chat surface
> shows and how it is worded.

---

## 1. Objective

The current live build (iteration-3, M8 v3) made the copilot feel like a real,
owned, multi-turn conversation — and in doing so it also put the *engineering
spike's operator instrumentation* on screen: a SESSION panel of cost/tokens/
latency/ids, per-answer footer chips with routing and grounding tokens, a
`$0/query` brag line, and system-worded "honest" notes. That is exactly backwards
for the persona the chat is meant to serve. **Iteration 4 strips the chat surface
back to what a non-technical retail user needs — a trustworthy, plain-language,
cited answer — and relocates every operator value to the homes that already exist
for it** (the audit admin view and Langfuse observability plane). The bar is
**ChatGPT-level simplicity — nothing more.** The grounding/fallback behaviour
stays fully *visible* (it is the product's whole point) but is **re-authored into
plain reassurance**, never system diagnostics. Nothing about the governed pipeline,
M6-scoped retrieval, or the audit/observability planes changes; this is a
surface-and-copy redesign governed by `.claude/rules/ux-surface.md` (updated
2026-11-02, which names the iteration-3 build as the violation to fix).

---

## 2. Personas & jobs-to-be-done

**Lead persona — the non-technical retail staff member.** Support or
merchandising; no coding background; does not know (or care) what "routing",
"grounding", "tokens", or a "thread id" are. They want answers they can trust and
act on, help asking better questions, and a way back to past conversations.
Everything below is designed for *this* reader; the other two PRD §2 personas are
served by the same shape without any operator instrumentation.

| Persona (PRD §2) | Representative question | Job the chat must do |
|---|---|---|
| **Support agent** *(lead)* | "Is this headphone's disconnection a known issue, and the common fix?" | find a cited answer over reviews/policy, fast, in plain words |
| Marketing / product | "Top 3 complaints about our wireless earbuds this quarter — is sentiment improving?" | themes + a readable trend, cited, no jargon |
| Executive | "Which categories have the worst rating-to-price ratio, and why?" | a numbers-backed explanation, cited, no system internals |

**Jobs-to-be-done (lead persona):**

- **JTBD-1 — Trust the answer.** *When* I get an answer to a work question, *I
  want* to see in plain language what sources it came from, *so that* I can act on
  it (or quote it to a customer) without second-guessing whether it was made up.
- **JTBD-2 — Understand when the system holds back.** *When* the system can't
  fully verify a written answer and shows me the exact words from the sources
  instead, *I want* that explained as "here's exactly what the sources say," *so
  that* I read it as extra trustworthiness, not as an error or a broken feature.
- **JTBD-3 — Ask a better question.** *When* I'm not sure how to phrase a query or
  what to ask next, *I want* a few suggested starters and follow-ups, *so that* I
  can get to a useful answer without knowing the "right" wording.
- **JTBD-4 — Return to past work.** *When* I come back to a case I was working
  earlier, *I want* to find and reopen that conversation, *so that* I don't have to
  re-ask from scratch.
- **JTBD-5 — Know I'm seeing the right data.** *When* I ask something, *I want* a
  quiet, plain reassurance of what I'm allowed to see ("answering as: support"),
  *so that* I trust the scope without being shown a governance mechanism.

---

## 3. The concrete iteration-3 UI gaps this fixes

Enumerated against the `ux-surface.md` worked-example inventory (2026-11-02),
each checked against the **live** components. Each gap = *shown today → why it
breaks the surface boundary → what the user should see instead.*

| # | Shown today (live component) | Why it violates the surface boundary | What the user should see instead |
|---|---|---|---|
| **G1** | **Whole SESSION panel** — Cost `$0.00xx`, Tokens, Latency, Thread id, User id, Provider "invisible" (`SessionCard.tsx`, mounted in `RoleRail.tsx`). | Pure operator instrumentation (cost/tokens/latency/ids) with zero meaning to a retail user; already lives in the audit view + Langfuse. | **Removed entirely** from chat. This data stays in the audit plane and observability plane only. |
| **G2** | **Per-answer footer chips** — a `⇋ <intent>` route pill, a `grounded (extractive)` / `grounded (llm)` / `none (unsupported)` ground pill, `⏱ <ms>`, `$<cost>`, a **`why ▾` expander**, and a `⚠ fallback: <issue>` note (`TrustStrip.tsx`). | Routing labels, grounding tokens, latency, cost, tool path, tokens, memory counts — every one is a pipeline diagnostic forbidden on the user surface. | **No chips.** A cited, grounded answer carries **no** badge. Only a *departure* from the ideal gets a short plain note (see G5). Trust comes from readable source chips (G6), not instrumentation. |
| **G3** | **`$0/query` tagline** in the brand line `grounded · cited · $0/query` (`BrandCard.tsx:9`). | A cost brag — an internal/operational figure dressed as a feature; meaningless and slightly untrustworthy to a retail user. | A plain product line only, e.g. **"grounded · cited"** (no cost). |
| **G4** | **Conversation header shows `<role> · <intent>`** — e.g. `executive · sql_rag` (`App.tsx:167`, rendered as `meta` in `ConversationPanel`). | The `· <intent>` half (`sql_rag`, `review_rag`, …) is a routing label; it leaks the pipeline's internal classification into the header. | **Role/scope half only**, worded as reassurance — e.g. "answering as: support" (JTBD-5). Drop the intent token. |
| **G5** | **System-worded honest states** — `"The data query failed, so metrics and trends are hidden…"`, `"Shown as a verbatim extract from the sources because the written answer could not be fully verified."`, plus raw grounding tokens (`extractive`, `llm draft blocked`) surfaced via the trust strip (`copy.ts`, `TrustStrip.tsx`). | The grounding/fallback feature is correct and must stay, but it is phrased in system terms ("data query failed", "verbatim extract", "could not be verified") — it reads as an error/warning dump to a non-technical reader. | **Re-authored as plain reassurance** (ux-surface "Honest messages must speak the user's language"): verbatim fallback → *"Here are the exact words from the sources"*; SQL/compute failure → *"We couldn't calculate the numbers for this one — here's what customers actually said."* No raw grounding tokens, ever. |
| **G6** | **Citations** rendered as `[n]` markers / chips tied to raw `source_id` (`CitationChips.tsx`, `EvidencePanel.tsx`); evidence identity is technical. | A retail user can't read a raw `source_id`; citation shouldn't require decoding. | **Human-readable source chips** — e.g. *"Source: return-refund policy"* — click to inspect the exact (already PII-redacted) snippet. Never raw JSON or ids. |
| **G7** | **Demo identity switcher styled as product chrome** at the rail top (`IdentitySwitcher.tsx`), sitting inline with real controls. | It exists only to demonstrate owner-scoping; styled as a feature, it misrepresents a demo affordance as something the retail user "uses" to log in. | Kept (it still proves owner-scoping) but **visibly marked demo-only and set apart** from product chrome, so it never reads as auth/account switching. |
| **G8** | **Unbounded growing transcript risk** — `StackedTurns` stacks all turns; the stream region must stay a fixed-height, auto-scrolled area (`ConversationPanel.tsx` has a `stream` ref + scroll-to-bottom; this must be the *enforced* layout, not incidental). | ux-surface "Layout": the conversation must be a bounded, scrollable region, newest at bottom — never an infinitely growing page. | A **fixed-height, scrollable transcript**, newest message at the bottom, auto-scrolled on each new answer; older turns reached by scrolling or via History. |

---

## 4. UX success criteria (measurable / checkable)

1. **Zero system internals on the chat surface.** Across any flow, the user never
   sees: `thread_id`/`session_id`, token counts, `cost_usd`, latency, an
   intent/routing label, `tool_path`, a model slug, a provider name, or any raw
   `audit` JSON. *(Checkable: audit the rendered DOM for each; count must be 0.)*
2. **Carry-forward acceptance criterion.** *A support agent can ask a question
   **and a vague follow-up**, and get cited answers, **without ever seeing a
   single system metric or internal id.*** *(Checkable: run the two-turn flow end
   to end; the whole surface stays clean.)*
3. **Every answer is trustable in one glance.** A grounded answer shows its
   evidence as **human-readable source chips**; one click on a chip reveals the
   exact redacted snippet — no jargon, no raw ids. *(Checkable: chip label is a
   plain phrase; click → snippet; no `source_id` string visible.)*
4. **Honest states read as reassurance, not errors.** When the system shows
   verbatim evidence instead of a synthesised answer (or can't compute numbers),
   the note is plain-language and contains **no** pipeline token (`extractive`,
   `sql_rag`, `llm draft blocked`, "query failed", etc.). *(Checkable: diff the
   rendered copy against the forbidden-token list; none present.)*
5. **Bounded, scrollable transcript.** The conversation lives in a fixed-height
   region, newest at the bottom, auto-scrolled on each new answer; the page itself
   never grows unbounded. *(Checkable: after N turns the page height is stable;
   the transcript scrolls internally.)*
6. **History is reachable and plain.** The user can see and reopen their past
   conversations (owner-scoped rail), and is offered suggested follow-up
   questions. *(Checkable: a past thread reopens; follow-up suggestions render.)*
7. **Scope reads as reassurance.** A quiet "answering as: support" style indicator
   is present and derived from the real scope, phrased in user terms ("You can see
   all categories" / a plain scope line) — never "retrieval is not filtered" or a
   governance mechanism. *(Checkable: copy contains no governance jargon.)*
8. **Demo control is unmistakably demo.** The identity switcher is textually and
   visually marked demo-only and separated from product chrome. *(Checkable: a
   first-time viewer identifies it as a demo control, not a login.)*

---

## 5. Scope & non-goals

**In scope:** the M8 chat *surface* and its copy — decluttering per §3, the
human-readable source-chip + inspectable-snippet treatment, plain-language honest
states, suggested starters/follow-ups, a reassurance-worded scope indicator, the
bounded scrollable transcript, the owner-scoped history, and marking the demo
switcher as demo-only.

**Never shown in the user surface (strip from chat — these already have homes):**
`thread_id` / `session_id`, token counts, `cost_usd`, latency, intent / routing
labels, `tool_path`, model slugs, provider names, any raw `audit` JSON. Their two
homes are unchanged: the **audit plane** (`audit_log`, via the role-gated audit
admin view) and the **observability plane** (Langfuse). Where a value helps the
user understand the *answer*, it is re-rendered as plain, grounded, cited content
— not as a system internal.

**Non-goals (no behaviour change — design must not outrun governance):**

- **No pipeline / retrieval / governance change.** Same M6-scoped retrieval, same
  grounding and PII redaction, same `audit` record. This iteration cannot design a
  surface that could show a role data its scope forbids; any analytics view is fed
  by the same scoped retrieval.
- **No new backend fields required.** The redesign binds to the already-shipped
  contract (`POST /query`, `audit.scope`, `citations[].snippet`, `GET /threads` /
  `GET /threads/{id}`). Exact bindings are deferred to `03_handoff.md`.
- **No real auth.** The identity switcher stays a *demo* owner selector (marked as
  such); real auth remains deferred (BACKLOG).
- **No thread management verbs** (rename / search / delete), **no streaming** —
  carried non-goals from iterations 2–3.
- **Not a rewrite of the conversation shell.** Iteration-3's history rail, stacked
  turns, and one-at-a-time evidence stay; iteration 4 declutters and re-words the
  surface around them.

---

*Next (gated on D1 approval): `design/iteration-4/01_wireframes.md` — lo-fi
annotated layouts for the decluttered surface and every state (empty, loading, a
clean grounded answer with source chips, the re-worded honest/fallback state, a
role-scoped answer, and the bounded scrollable transcript). This is a brief only —
no pixels.*
