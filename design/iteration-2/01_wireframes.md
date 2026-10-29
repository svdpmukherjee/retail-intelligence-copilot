# 01 · Wireframes — M8 Chat / Serving UI

**Design Track · iteration 2 · Stage D2-prep (lo-fi).** Annotated box layouts
only — no color, type, or polish. The hi-fi mockup is the next stage. Every
element here traces to a real field in the `POST /query` response
(`answer`, `citations[]`, `audit{}`, `thread_id`, `user_id`) or `GET /roles`.
Where a needed signal is **not** in the response, it is flagged `⚑ HANDOFF` for
`03_handoff.md` rather than invented (brief §5: no UI fabrication).

Field legend used in callouts: `A.x` = `audit.x`; `C[]` = `citations[]`;
`R.x` = top-level response field.

---

## 0. Field → source map (the contract this wireframe binds to)

| UI signal | Real field | Notes |
|---|---|---|
| Answer body | `R.answer` | may be multi-line; one claim per line, each ends in `[n]` |
| Citation chip `[n]` + label + snippet | `C[].n`, `C[].label`, `C[].source_id` | snippet text is **not** a response field ⚑ |
| Route badge | `A.intent` | `sql` / `review_rag` / `docs_rag` / `sql_rag` |
| Tool path | `A.tool_path[]` | e.g. `["sql_agent","review_rag"]` |
| Grounding state | `A.grounding.path` | `llm` / `extractive` / `none` |
| Grounding issues | `A.grounding.issues[]` | e.g. `"llm draft blocked"` |
| Evidence ids | `A.sources[]` | `"sql"` + chunk ids |
| Role | `A.role` | echoed caller role |
| Cost / tokens / latency | `A.cost_usd`, `A.tokens`, `A.latency_ms` | |
| Degraded compute | `A.sql_error` | present only when SQL failed |
| Memory | `A.memory.history_turns_used`, `A.memory.persisted` | present only when memory on |
| Role list (picker) | `GET /roles` → `roles[]` | names only |
| Thread continuity | `R.thread_id`, `R.user_id` | round-tripped into next request |

### ⚑ HANDOFF items surfaced by this stage (gaps in the current contract)

1. **Citation snippet text is not returned.** `C[]` carries `n`, `source_id`,
   `label` only; the evidence *quote* is embedded inside `R.answer` for the
   `extractive` path and absent for the `llm` path. Wireframes below show an
   inspectable snippet; Developer needs either a `citations[].snippet` field or
   a documented rule for deriving it. **Do not fabricate a snippet.**
2. **Scope categories per role are not exposed.** `A.role` gives the role name;
   the allowed categories (`ACCESS_POLICY`) live server-side only, and
   `GET /roles` returns names without scope. The "filtered to your categories"
   affordance (criterion 3) needs a role→categories map or a `scope` field on
   the response. Until then the UI can state *that* a scope applies (from role)
   but not enumerate categories without a new field.
3. **Degradation is signalled only by presence.** `A.sql_error` and
   `grounding.path == "none"` are the only degradation flags; there is no
   severity/user-message field. UI must author the human copy from these.

---

## 1. Overall layout — the chat surface

Three regions. The **"why-this-answer"** detail is placed as an **inline
expandable trust strip** attached to each assistant turn, with a **docked
Evidence panel** on the right for citation inspection.

**Why this placement (justification).** A persistent full audit sidebar would
bury the answer and read as a developer console (v1's failing was the opposite:
nothing). Per-turn inline keeps trust *with the claim it explains* and satisfies
criterion 1 ("one action"): the strip header is always visible (route +
grounding + $0), one click expands the rest. Citations need more room and
cross-reference, so inspecting a `[n]` opens the right Evidence panel rather
than growing the bubble. On phone width the Evidence panel becomes a bottom
sheet (see §9).

```
┌──────────────┬───────────────────────────────────────────┬───────────────┐
│  ROLE RAIL   │             CONVERSATION THREAD            │ EVIDENCE PANEL│
│  (left)      │               (center, scrolls)            │ (right, dock) │
│              │                                            │               │
│ Persona ▾    │  ┌─ user turn ───────────────────────┐    │  collapsed by │
│  ○ support   │  │ "Is the disconnection a known…"   │    │  default;     │
│  ● marketing │  └───────────────────────────────────┘    │  opens when a │
│  ○ executive │                                            │  citation [n] │
│              │  ┌─ assistant turn ──────────────────┐    │  is clicked   │
│ ── scope ──  │  │ answer text … [1] … [2]           │    │               │
│ Filtered to  │  │                                   │    │  shows C[]    │
│ your scope   │  │ [1][2] citation chips             │    │  label +      │
│ (role-based) │  │ ┌ trust strip (collapsed) ──────┐ │    │  snippet ⚑    │
│  A.role      │  │ │ ⟐ route · ⛨ grounded · $0 ▾ │ │    │  + source_id  │
│              │  │ └───────────────────────────────┘ │    │               │
│ ── session ─ │  └───────────────────────────────────┘    │               │
│ thread_id…   │                                            │               │
│ (R.thread_id)│  ┌─ composer ────────────────────────┐    │               │
│ user_id…     │  │ [ ask a question…        ] (send) │    │               │
└──────────────┴──└───────────────────────────────────┘────┴───────────────┘
```

Region bindings:
- **Role rail** — persona picker populated from `GET /roles` → `roles[]`
  (support / marketing / executive are the PRD §2 drivers; admin/analyst
  secondary). Selected role is sent as `req.role` and echoed back as `A.role`.
  Scope line and session block also live here.
- **Thread** — alternating user / assistant turns; each assistant turn carries
  its own citation chips + trust strip. `R.thread_id` + `R.user_id` are
  round-tripped so follow-ups share memory.
- **Composer** — single input → `POST /query { query, role, thread_id, user_id }`.
- **Evidence panel** — opens on citation click; renders `C[]` for the active
  turn.

---

## 2. Empty / first-run state

Nothing asked yet. Orients the *current persona* with example questions drawn
from PRD §2 (static starter prompts, not a response field).

```
┌──────────────┬───────────────────────────────────────────┬──────────────┐
│ ● support    │                                            │ Evidence     │
│              │        ╭───────────────────────────╮       │ (empty)      │
│ scope: your  │        │  Retail Intelligence      │       │              │
│ categories   │        │  Copilot                  │       │ "Ask a       │
│ (role-based) │        │  Grounded · cited · $0/qry│       │  question —  │
│              │        ╰───────────────────────────╯       │  evidence    │
│              │                                            │  for the     │
│              │   Try (for your role):                     │  answer      │
│              │   ┌─────────────────────────────────────┐  │  appears     │
│              │   │ "Is this headphone's disconnection  │  │  here."      │
│              │   │  a known issue, and the common fix?"│  │              │
│              │   └─────────────────────────────────────┘  │              │
│              │   ┌─────────────────────────────────────┐  │              │
│              │   │ "What does the returns policy say…" │  │              │
│              │   └─────────────────────────────────────┘  │              │
│              │                                            │              │
│              │  ┌ composer ─────────────────────────┐    │              │
│              │  │ [ ask a question…         ] (send)│    │              │
└──────────────┴──└───────────────────────────────────┘────┴──────────────┘
```
Notes:
- Starter prompts are **persona-conditioned by role** (support ↔ marketing ↔
  executive) — switching the picker swaps the example set. The examples are
  authored UI copy (PRD §2), not response data; no fabrication of answers.
- Cost headline "$0/query" is a brand truth (`A.cost_usd` will confirm per turn,
  brief §4.6) shown here as a promise, labelled as such.

---

## 3. In-flight / loading state

The user turn is committed; the assistant turn is a skeleton. No answer, no
citations, no audit yet — nothing is shown as known until the response lands.

```
┌─ user turn ─────────────────────────────┐
│ "Top 3 complaints about our earbuds…"   │
└─────────────────────────────────────────┘
┌─ assistant turn (pending) ──────────────┐
│  ▟▙ routing → retrieving (scoped) →     │   ← staged labels are generic
│     grounding … answer                  │     process copy, NOT field reads
│  ░░░░░░░░░░░░░  (skeleton lines)         │     (A.tool_path is unknown until
│  [ cancel ]                             │      the response returns)
└─────────────────────────────────────────┘
```
Notes:
- The staged labels ("routing → retrieving → grounding") describe the *known
  pipeline shape*, not live telemetry — the backend returns once, not as a
  stream (brief §5: no streaming). They must read as a generic progress hint,
  never as a claim about `A.tool_path` for this turn.
- Composer disabled while in flight; `[cancel]` aborts the request.

---

## 4. Grounded answer state (the default good answer)

The core screen. Answer + inspectable citations + one-click trust reveal.

```
┌─ assistant turn ───────────────────────────────────────────────────────┐
│ Disconnection on this model is a widely reported issue. [1]            │ ← R.answer
│ The documented fix is to re-pair after a firmware update. [2]          │   (per-line
│                                                                        │    claims)
│  evidence:  [1 review B00XX (Electronics)]  [2 Returns Policy / §3]    │ ← C[].n + .label
│             click a chip → opens Evidence panel                        │   (chips)
│ ┌ trust strip  (collapsed — always visible) ───────────────────────┐  │
│ │ ⟐ review_rag   ⛨ grounded (llm)   ⏱ 420ms   $0.00        [ why ▾]│  │ ← A.intent,
│ └───────────────────────────────────────────────────────────────────┘  │   A.grounding.path,
│ ┌ trust strip  (EXPANDED after one click on [why ▾]) ───────────────┐  │   A.latency_ms,
│ │ route (intent) : review_rag                        A.intent       │  │   A.cost_usd
│ │ tool path      : sql_agent → review_rag            A.tool_path[]  │  │
│ │ grounding      : llm (model-written, cite-checked) A.grounding    │  │
│ │ evidence used  : 2 sources  (sql, B00XX…)          A.sources[]    │  │
│ │ tokens         : 1,240   cost: $0.00   latency: 420ms             │  │
│ │ memory         : used 1 prior turn · persisted     A.memory.*     │  │
│ └───────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘

Evidence panel (right), when chip [1] clicked:
┌ EVIDENCE ─────────────────────────┐
│ ● [1]  review B00XX (Electronics) │ ← C[].label
│    source_id: B00XX#0             │ ← C[].source_id
│    ┌───────────────────────────┐  │
│    │ "…keeps disconnecting      │  │ ← snippet ⚑ HANDOFF #1
│    │  after 10 min…"            │  │   (not a response field today)
│    └───────────────────────────┘  │
│   [2]  Returns Policy / §3        │
└───────────────────────────────────┘
```
Interactions:
- **One click = criterion 1.** `[why ▾]` toggles the expanded strip revealing
  `A.intent`, `A.tool_path`, `A.grounding.path`. No scroll, no log.
- **Citations inspectable = criterion 2.** Chip click opens Evidence panel with
  `C[].label` + `C[].source_id`; snippet body is the ⚑ handoff gap.
- Collapsed strip always shows route + grounding + cost/latency so trust is
  glanceable without the click.

---

## 5. Role-adaptive answer shapes (same surface, three renders)

Same `POST /query`; the assistant-turn **template is chosen by `A.role` +
`A.intent`**. Only the body layout changes — the citation chips + trust strip
are identical across all three (shown abbreviated here).

### 5a. Support — snippet + governing policy  (`intent: review_rag`/`docs_rag`)
```
┌─ assistant turn (support) ───────────────────────────────┐
│ ▸ ISSUE   Known issue: Bluetooth disconnection. [1]      │ ← R.answer line 1
│ ▸ FIX     Re-pair after firmware update. [1]             │
│ ┌ governing policy ─────────────────────────────────┐   │ ← the docs_rag citation
│ │ Returns Policy / §3  —  "30-day return if …" [2]  │   │   surfaced as a quotable
│ └───────────────────────────────────────────────────┘   │   card (C[] where label
│ [1 review…] [2 Returns Policy/§3]   ⟐ review_rag · ⛨ ▾ │   is a doc)
└──────────────────────────────────────────────────────────┘
```

### 5b. Marketing — theme list + trend  (`intent: sql_rag`)
```
┌─ assistant turn (marketing) ─────────────────────────────┐
│ Top complaints this quarter: [1]                         │ ← R.answer (themes)
│  1. battery life          2. fit        3. connectivity  │
│ ┌ trend (from SQL) ──────────────────────────────────┐  │ ← the SQL citation
│ │ sentiment  ▁▂▃▄▅  improving   (source: SQL [1])    │  │   (C[] source_id="sql")
│ │  lo-fi bars = placeholder; hi-fi renders inline chart│  │   rendered as a trend
│ └─────────────────────────────────────────────────────┘  │   strip, labelled "from
│ [1 SQL result] [2 review…]   ⟐ sql_rag · ⛨ grounded ▾ │   SQL"
└──────────────────────────────────────────────────────────┘
```

### 5c. Executive — headline + ranked metric + one-line cause (`intent: sql_rag`)
```
┌─ assistant turn (executive) ─────────────────────────────┐
│ ❝ Books have the worst rating-to-price ratio. ❞ [1]      │ ← R.answer line 1 = headline
│ ┌ ranked metric (SQL) ───────────────────────────────┐  │
│ │ 1. Books        2.1 ★ / $     ▇▇            [1]     │  │ ← SQL citation as ranked
│ │ 2. Toys         2.8 ★ / $     ▇▇▇▇                  │  │   table (C[] source_id=sql)
│ │ 3. Beauty       3.4 ★ / $     ▇▇▇▇▇▇               │  │
│ └─────────────────────────────────────────────────────┘  │
│ why: low ratings concentrated in mass-market titles. [2] │ ← R.answer cause line (RAG)
│ [1 SQL result] [2 review…]   ⟐ sql_rag · ⛨ grounded ▾ │
└──────────────────────────────────────────────────────────┘
```
Notes:
- The **router chooses which chart/structure is even possible** via `A.intent` —
  a trend/metric strip appears only when `"sql"` is in `A.sources[]`. No chart
  is drawn from data the response didn't carry; charts read `C[]`/`A.sources`
  only (criterion 4, brief §5).
- All three are **the same backend answer** reshaped; switching persona and
  asking a comparable question is the demonstrable criterion-4 proof.

---

## 6. Scope-legible state

For a **scoped** persona (support, marketing), the view states that evidence was
filtered to the role's categories *at retrieval, before the model*. Executive
(unrestricted) shows the complementary "all categories" note.

```
Role rail (scoped persona):
┌──────────────────────────┐
│ ● marketing              │
│ ── scope ──              │
│ 🔒 Filtered to your      │ ← derived from A.role (role is scoped)
│    categories            │
│    at retrieval, before  │   copy is fixed; it never says data was
│    the model             │   "hidden" — it says the search was scoped
│  [ what's this? ⓘ ]      │   (brief §4.3)
│    ⚑ category NAMES need │ ← ⚑ HANDOFF #2: cannot enumerate categories
│      a scope field       │   without a new response/API field
└──────────────────────────┘

Inline scope ribbon on the answer (scoped persona only):
┌─ assistant turn ─────────────────────────────────────────┐
│ 🔒 Answered from evidence inside your role's scope.       │ ← presence driven by
│    Retrieval was filtered server-side, before the model.  │   A.role being a scoped
│ … answer … [1]                                            │   role; not a toggle
└───────────────────────────────────────────────────────────┘
```
Notes:
- Scope is **not a control** — no checkbox, no "show all". It is a read-only fact
  of the persona (brief §5: UI must never offer a path around M6).
- Tooltip `ⓘ` explains "before the model" in one sentence. The ribbon appears
  for scoped roles only; executive sees "Unrestricted — all categories" instead.
- Enumerating the actual category names is blocked on ⚑ HANDOFF #2.

---

## 7. Graceful-degradation state

Two independent degradations, each with authored copy and both still honest
about what *did* ground.

### 7a. SQL could not compute — `A.sql_error == "could not compute"`
```
┌─ assistant turn ─────────────────────────────────────────┐
│ ⚠ Couldn't compute the numbers for this one.             │ ← A.sql_error present
│   Answering from the review evidence instead. [1]         │
│ … theme answer … [1]                                      │ ← R.answer (RAG leg
│ [1 review…]   ⟐ sql_rag · ⛨ grounded (partial) ▾        │   still grounded)
│   trust strip → shows: sql_error: could not compute       │
└───────────────────────────────────────────────────────────┘
```
The metric/trend strip from §5b/5c is **suppressed** (no `"sql"` in
`A.sources[]`), replaced by the warning line. The RAG answer still renders +
cites.

### 7b. No supporting evidence — `A.grounding.path == "none"`
```
┌─ assistant turn ─────────────────────────────────────────┐
│ ○ No supporting evidence was found for this question.     │ ← R.answer (composer's
│                                                            │   none-path message)
│   Nothing in your scope matched — try rephrasing, or ask  │
│   something your role covers.                             │
│ (no citation chips — C[] is empty)                        │ ← C[] == []
│ ┌ trust strip ──────────────────────────────────────┐    │
│ │ grounding : none (unsupported)   A.grounding.path │    │
│ │ evidence  : 0 sources            A.sources == []  │    │
│ └────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```
Notes:
- `none` is a *legitimate, designed answer*, not an error — no red error banner.
- If `A.grounding.issues[]` is populated (e.g. `"llm draft blocked"`), the trust
  strip lists them under "grounding issues" so a reviewer sees *why* a draft was
  rejected (criterion 2). This can co-occur with a normal grounded answer (draft
  blocked → fell back to extractive); shown as a small "fallback" note on the
  collapsed strip.

---

## 8. Error states — `400` vs `502` (distinct, criterion 5)

These are HTTP failures from `POST /query`, not assistant turns. `detail` is the
JSON error body.

### 8a. 400 — input error (unknown role / AccessDenied)
```
┌─ banner (near composer) ──────────────────────────────────┐
│ ✦ Can't run that request.                                 │ ← HTTP 400
│   Unknown role: 'buyer'          (detail)                 │ ← detail string
│   Pick a valid role from the list and try again.          │
│   [ reselect role ]                                        │ ← actionable: points at
└────────────────────────────────────────────────────────────┘   the role rail
```
Fix is in the user's hands → directs to the role picker. No retry button (retry
won't help an invalid role).

### 8b. 502 — upstream failure (`PipelineError`)
```
┌─ banner (near composer) ──────────────────────────────────┐
│ ⚡ The copilot had an upstream problem.                    │ ← HTTP 502
│    Upstream failure: <type>: <msg>   (detail, truncated)  │ ← detail string
│    Your question wasn't changed — you can retry.          │
│    [ retry ]            [ copy details ]                   │ ← retry re-POSTs same
└────────────────────────────────────────────────────────────┘   query+thread_id
```
Differences made visible: 400 = *your input* (reselect role, no retry);
502 = *our pipeline* (retry same request). A bare `500` ("Query failed") maps to
the 502 treatment with generic copy. The user turn is preserved in both so
nothing is lost.

---

## 9. Phone width (reflow note, lo-fi)

At phone width the three columns stack: role rail collapses to a top bar with a
persona dropdown + scope lock icon; Evidence panel becomes a **bottom sheet**
that slides up on citation tap; trust strip behaves identically (inline
expand). 16px gutter; thread is the full-width primary. Composer pins to bottom.

```
┌───────────────────────────┐
│ ● marketing ▾   🔒 scope  │ ← collapsed rail (top bar)
├───────────────────────────┤
│ thread (full width) …     │
│  answer … [1][2]          │
│  [ why ▾ ]                │
├───────────────────────────┤
│ [ ask…            ](send) │ ← pinned composer
└───────────────────────────┘
      ↑ tap [1] → bottom sheet rises with C[] evidence
```

---

*Next (after review): `mockups/<surface>.html` (hi-fi, D2). The ⚑ HANDOFF items
(citation snippet text; role→category scope field; degradation copy) carry
forward to `03_handoff.md`.*
