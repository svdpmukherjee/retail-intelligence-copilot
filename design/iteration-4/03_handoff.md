# 03 · Build Handoff — M8 Chat / Serving UI (v4)

**Design Track · iteration 4 · Stage 5 (build spec).** The Developer implements
the M8 **v4** declutter + trust redesign from *this* document. It is a **delta**
on the iteration-2 and iteration-3 handoffs, which the v4 build still follows for
everything not named here (contract §0, state machine, role shapes, the
conversation shell, one-at-a-time evidence, a11y base). **Exactly one backend
field is added** — `citations[].display_label` (D-30); everything else binds to
the already-shipped contract. This is otherwise a frontend-and-copy redesign.

> **The one-line scope:** take the working iteration-3 surface and *remove* the
> operator instrumentation, *re-word* the honest states, and *render citations as
> readable source chips* — without touching the pipeline, retrieval, governance,
> or the `GET /threads` endpoints already in place.

---

## 1. Component inventory (delta on iteration-3 §3)

### REMOVE
| Component / element | File (live) | Why |
|---|---|---|
| **SessionCard** (Cost/Tokens/Latency/Thread/User/Provider) | `components/SessionCard.tsx` + its mount in `RoleRail.tsx` | Operator instrumentation; lives in audit plane + Langfuse (D-22). Delete the component and its rail slot. |
| **TrustStrip** (route pill, `grounded (…)` pill, latency pill, cost pill, `why ▾` expander, `⚠ fallback:` note, expanded Tool path / Tokens / Cost / Latency / Memory / SQL error body) | `components/TrustStrip.tsx` | Every field is a pipeline diagnostic (D-23). Remove the component entirely; do **not** replace with a "grounded" badge. |
| **ScopeCard** technical flags (`restricted`, raw category slugs, "retrieval filtered") | `components/ScopeCard.tsx` as rendered in the rail | Replaced by the derived plain scope line (D-26b). The ScopeCard *data source* (`audit.scope`) is reused, its technical presentation is not. |

### MODIFY
| Component | File | Change |
|---|---|---|
| **BrandCard** tagline | `components/BrandCard.tsx:9` | `grounded · cited · $0/query` → **`grounded · cited`** (drop `$0/query`) (D-24). |
| **ConversationPanel** header | `components/ConversationPanel.tsx`; `App.tsx:167` (`meta`) | Replace the mono `meta = "<role> · <intent>"` with a plain **"answering as: &lt;role&gt;"** pill — role only, no intent (D-24). Derive role from `audit.role` / active identity. |
| **CitationChips** → **source chips** | `components/CitationChips.tsx` | Render `Source: <display_label>` from the new `citations[].display_label` (D-30), not `[n]` + `source_id` and not `label`. Keep click-to-inspect; active chip highlighted; one active at a time across the thread (D-26). |
| **EvidencePanel** copy & item | `components/EvidencePanel.tsx` | Show one source: readable title (`citations[].display_label`) + redacted `snippet`. Remove the raw `source_id`/`eid` line and the mono type tag. Empty prompt → "Tap a Source on any answer to read the exact words it came from." `null` snippet → plain "the exact words aren't available to show." (D-26) |
| **IdentitySwitcher** label + styling | `components/IdentitySwitcher.tsx` | Options read **`user_id (<team> team)`**: "support_1 (support team)", "support_2 (support team)", "marketing_1 (marketing team)", "executive_1 (executive team)" (NOT "user_id — role") (D-27). Set apart as demo: dashed border, "⚙ demo — not a login" tag, the not-part-of-the-product note. |
| **copy.ts** honest-state strings | `copy.ts` | Re-author (D-25a): `FALLBACK_NOTE` → "Here are the exact words from the sources:"; `SQL_DEGRADED` → "We couldn't calculate the numbers for this one — here's what customers actually said:"; `NO_EVIDENCE` → "I couldn't find anything about that in the sources you have access to. Try rephrasing, or ask about a different product or topic." Remove `STAGES` from the loading view (no stage pipeline); add a system-error string. Keep `startersFor`; keep `evidenceType` only if still needed internally (not shown as a tag). |

### UNCHANGED (inherited; do not re-open)
`HistoryRail` / `HistoryDrawer` (owner-scoped list, `+ new chat`, reopen, phone
drawer), `StackedTurns` (bounded auto-scroll container), the composer, the
`EmptyState` scaffold (restyled copy only), `LoadingState` (minus the stage
pipeline), `ThemeToggle`, the `api/` layer, `GET /threads` + `GET /threads/{id}`,
and the three role shapes (`shapes/*`) — re-skinned to the decluttered language
but structurally the same; charts still gated on `"sql" ∈ audit.sources[]` and
scope never widened client-side.

---

## 2. States and render rules

Honest-state selection is **derived from field presence, never from answer text**
(matches the existing `copy.ts` contract). Selection order:

1. **Empty / new chat** — no turns. Render the brand logo, plain tagline ("Every
   answer comes with the exact sources it's based on — nothing made up."), the
   **derived scope line** (`scopeLine(audit.scope)` / `scope_for_role` before the
   first query), and 2 role-appropriate **starters** (`startersFor(role)`). No
   metrics, no role·intent.
2. **Loading** — the question echoed as a user turn + one plain line **"Looking
   through the sources…"** with a spinner. **No STAGES pipeline.** Composer
   disabled.
3. **Clean grounded answer** — `grounding.path === "llm"` and no `sql_error`.
   Render `answer` + **source chips** + follow-ups. **No note, no badge** (D-25b).
4. **Exact-words / verbatim** — `grounding.path === "extractive"`. Lead "Here are
   the exact words from the sources:" + the quoted evidence (calm accent border,
   not a warning) + source chips. No `extractive` token on screen.
5. **Numbers unavailable** — `audit.sql_error` present. Lead "We couldn't
   calculate the numbers for this one — here's what customers actually said:" +
   the review-grounded `answer` + source chips. No `sql_error` string, no empty
   chart slot.
6. **Nothing found** — `grounding.path === "none"` / no citations. Plain "I
   couldn't find anything about that in the sources you have access to." + one
   recovery suggestion. No chips.
7. **System error** — request/network/HTTP failure (caught in the `api/` layer per
   the frontend code-style rule). Plain "Something went wrong getting that answer.
   Please try again in a moment." + a **Try again** button. **Never** render the
   HTTP status, `detail` payload, provider, or a trace id — operator detail stays
   in the audit/observability planes.

Follow-ups and starters are presentation only; they post ordinary `POST /query`
calls through the unchanged pipeline.

---

## 3. Data bindings (already-shipped contract + ONE new field: `display_label`)

Verified against `frontend/src/api/types.ts` (mirrors `backend/app/main.py` +
`agents/composer.py`). **Field names are load-bearing — use these exactly.**
v4 adds **exactly one** backend field, `citations[].display_label` (D-30); the
rest of the contract is unchanged.

`POST /query` → `QueryResponse` the surface reads:

| Rendered element | Exact field | Notes |
|---|---|---|
| Answer body | `answer: string` | plain-language answer; role shape chooses layout only. |
| Source chip **label** | **`citations[].display_label: string`** (NEW) | the human-readable chip text → render as `Source: <display_label>`. Raw ids/ASINs/slugs **never** reach the chip. Derived server-side (see below). |
| (internal) answer-text / prompt label | `citations[].label: string` (**unchanged**) | kept as-is — still used by the extractive answer text and the LLM prompt. **Not** rendered on the chip. Preserving it means no regression in answer composition. |
| Inspect **snippet** | `citations[].snippet: string \| null` | the PII-redacted excerpt, shown verbatim on chip click; `null` → "exact words aren't available to show". Never un-redact or fabricate. (Unchanged.) |
| (internal) citation identity | `citations[].n`, `citations[].source_id` | used only as React keys / active-chip tracking; **never displayed**. |
| Scope line + "answering as" | `audit.scope: { restricted: bool, categories: string[] }` | derive the plain scope sentence from it; role from `audit.role`. Never hard-code category names; never widen. |
| Honest-state selection | `audit.grounding.path` (`llm`/`extractive`/`none`), `audit.sql_error?` | drive which state renders (§2); **never rendered as text**. |
| Analytics layout gate | `audit.sources[]` contains `"sql"` | gate charts (inherited); still scoped. |
| Continuity (internal) | `thread_id`, `user_id` round-trip | kept in app state for follow-ups; **never displayed**. |

`GET /threads?user_id=&role=` → `ThreadListItem[]` (`id`, `label`, `created_at`,
`turn_count`): history rows show `label` (text) + `created_at` (relative time).
`turn_count` may inform a subtle hint but is **not** shown as a metric. `id` round-
trips on reopen; **never displayed**.

`GET /threads/{id}?user_id=` → `ThreadDetail` (`turns[].role_kind`, `.content`):
reopened turns render stored text. Restored assistant turns have **no stored
`citations`/`audit`** → they show the answer text with **no source chips** (honest
degradation, inherited D-21); do not fabricate chips. (The mockup shows chips on
reopened threads as a flagged canned convenience only.)

### 3.1 The one backend edge — `citations[].display_label` (D-30)

Add a new field `display_label: str` to the `Citation` model (`composer.py`) and
to the `POST /query` `citations[]` contract, **distinct from the existing
`label`** (which stays unchanged for answer-text / LLM-prompt use). The chat
source chip binds to `display_label` only. Derive it server-side in the composer,
**by source type**, from category/title metadata only — never from raw user text:

| Source type | `display_label` derivation |
|---|---|
| **review** | Drop the raw ASIN. Use `"customer review · <Category>"` — category underscores→spaces, title-cased (e.g. `Home_and_Kitchen` → `customer review · Home and Kitchen`). If a product title is available, use that instead. |
| **doc** | A prettified human title (NOT the slug/filename), optionally `"<Title> · <Section>"` (e.g. `returns_policy#3` → `Return & Refund Policy · §3`). |
| **SQL** | `"Calculated from your data"` (instead of "SQL result"). |

**PII-safe by construction:** `display_label` is derived from category / product
title / document title only — **no raw review or user text** flows into it — so it
is safe to render unredacted on the chip. (The redacted `snippet` remains the only
place verbatim source text appears, and it is already PII-redacted at source.)

**This is the only new field.** Everything else binds to the already-shipped
contract; the inspect-snippet binding stays on `citations[].snippet`.

**Still open (flag, do not invent):**
- **Restored-turn source chips** need per-turn `citations` persisted (i3 §2
  option c) — an open backend change, out of scope for v4.

---

## 4. Role → render rules

- Same **M6-scoped retrieval**; the surface renders only what the scoped pipeline
  returns and **never shows data outside the active role's scope**. Any
  chart/analytics view is fed by the same scoped retrieval — design must not
  outrun governance.
- **Scope line + "answering as: &lt;role&gt;"** are derived from `audit.scope` /
  the active role; the UI never widens scope client-side and never hard-codes
  category names.
- The **demo switcher is the owner selector only** (`user_id` + its team label);
  it is not auth, it does not grant scope — scope still comes from the server's
  `audit.scope`. Switching identity reloads the owner-scoped `GET /threads` and
  resets the center to that owner's empty state (nothing from the prior owner
  lingers).
- Role shapes (support / marketing / executive) choose **presentation only**;
  shape selection and chart gating are inherited unchanged.

---

## 5. Forbidden-on-surface list (acceptance gate for Developer + Tester)

The following must appear **nowhere** on the user chat surface (DOM-checkable;
expected count **0** each): `thread_id`, `session_id`, token counts, `cost_usd`,
`latency_ms`, `intent` / routing labels, `tool_path`, model slugs, provider
names, raw `audit` JSON, and the raw grounding tokens (`extractive`, `llm`,
`none`, `sql_rag`, `llm draft blocked`, "query failed", "not filtered",
"no session trust").

**Carry-forward acceptance criterion (must pass):** a support agent can ask a
question **and a vague follow-up**, and get cited answers, **without ever seeing a
single system metric or internal id.** Test path: ask "What is the return
policy?" → cited answer with source chips; ask the vague follow-up "And what about
opened electronics?" → cited answer; assert the forbidden list count is 0
throughout and both turns show readable source chips whose click reveals a
redacted snippet.

---

## 6. Accessibility (delta on iteration-3 §5; base holds in full)

| Requirement | Where |
|---|---|
| `:focus-visible` rings on all interactive controls | global (inherited). |
| **Source chips are real `<button>`s** | keyboard-reachable; active chip conveys state non-colour-only (text/weight), not colour alone. |
| `aria-live="polite"` on the stream | a newly-appended turn is announced once rendered (no stream transport). |
| Evidence **bottom sheet** (phone) focus | opening moves focus into the sheet; **Escape closes** and returns focus to the chip that opened it; backdrop click closes. |
| History **drawer** (phone) focus | `☰` has `aria-expanded`; opening moves focus into the drawer; Escape + backdrop close and return focus to the toggle. |
| Active history row | real `<button>` with **`aria-current="true"`** on the open thread. |
| Reduced motion | `prefers-reduced-motion` disables the spinner/scroll animations (inherited). |
| Layout | 16px side gutters, no horizontal scroll, works at phone width (inherited). |
| Demo switcher labelled | the `<select>` has an accessible name; "demo — not a login" is textually present, not colour-only. |

---

*Sources of truth: `frontend/src/api/types.ts` (`QueryResponse`, `Citation.label`
[unchanged] + new `Citation.display_label`/`.snippet`,
`Audit.scope`/`.grounding`/`.sql_error`, `ThreadListItem`,
`ThreadDetail`), `backend/app/main.py` (`POST /query`, `GET /threads`,
`GET /threads/{id}`), `agents/composer.py` (`Citation`, `display_label`
derivation, `_snippet`),
`agents/pipeline.py` (`audit.scope`). Design: `i4/00_brief.md`,
`i4/01_wireframes.md`, `i4/02_decisions.md`, `i4/mockups/m8-chat.html` (approved
D2). Governing rule: `.claude/rules/ux-surface.md`. Inherited specs:
`design/iteration-2/03_handoff.md`, `design/iteration-3/03_handoff.md`.*
