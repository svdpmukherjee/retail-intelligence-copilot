# 03 · Build Handoff — M8 Chat / Serving UI (v2)

**Design Track · iteration 2 · Stage 5 (build spec).** The Developer implements
M8 v2 from *this* document — it is self-contained; you should not need to re-read
the mockup source. The mockup (`mockups/m8-chat.html`, approved D2) is the visual
reference; this spec names every component, state, and **exact backend field** it
binds to.

> **Scope of the rebuild.** v1 shipped a minimal React/Vite chat
> (`frontend/src/App.tsx`, `components/MessageList.tsx`, `components/Citations.tsx`,
> `api/client.ts`, `api/types.ts`). It renders `answer` + `[n] label` and a single
> generic error string; it discards all of `audit`. v2 replaces the UI surface
> while reusing the working API layer. **Do not change the backend pipeline** —
> only the 3 pending fields in the Pending section are candidate backend edges,
> and each is flagged frontend-only vs backend-change.

---

## 0. The contract this build binds to (verified against `backend/`)

`POST /query` request — `QueryRequest` (main.py):
```
{ query: string, role: string, thread_id?: string|null, user_id?: string|null }
```
`POST /query` response — `QueryResponse` = `AnswerResult` + thread fields:
```
answer: string                 # composer.py — one claim per line, each line ends with [n]
citations: Citation[]          # only cited numbers survive (composer filters to used [n])
audit: object                  # see below; a plain dict, keys added in pipeline.py
thread_id: string | null
user_id:   string | null
```
`Citation` (composer.py) — **verified fields are exactly**:
```
n: number
source_id: string              # chunk id (e.g. "B07...#2") or the literal "sql"
label: string                  # "review <asin> (<category>)" or "<doc_title> / <section>" or "SQL result"
```
> ⚠ **`source_type` is NOT a field on `Citation` today.** The mockup shows a
> small type tag ("review"/"policy"/"sql") in the Evidence panel; that value is
> *derived* in the mockup, not returned. See Pending field #3.

`audit` object — keys set in `pipeline.py` / `composer.py` (all present on a
normal turn unless noted):
```
query:        string
role:         string                       # echoed caller role
intent:       "sql" | "review_rag" | "docs_rag" | "sql_rag"
tool_path:    string[]                      # e.g. ["sql_agent","review_rag"]
sources:      string[]                      # ["sql"]? + chunk ids used by the answer
tokens:       number
cost_usd:     number                        # 0 in free mode
latency_ms:   number
grounding:    { path: "llm" | "extractive" | "none", issues: string[] }
sql_error?:   "could not compute"           # present ONLY when the SQL leg degraded
memory?:      { thread_id, history_turns_used: number, persisted: number, error?: string }
                                            # present ONLY when memory is on for the turn
```
`GET /roles` → `{ roles: string[] }` (names only; no scope).

Error bodies: `ApiError{ status, detail }` already modeled in `api/client.ts`.
- `400` — `detail` = `"Unknown role: 'x'"` or an `AccessDenied` message.
- `502` — `detail` = `"Upstream failure: <Type>: <msg>"`.
- `500` — `detail` = `"Query failed"` (treat as 502).

---

## 1. Component inventory

Each component, its purpose, and the region it lives in. (Layout: 3-column shell
`236px | 1fr | 300px`; collapses to 2 columns `<1080px` — Evidence dock hides and
opens as a bottom sheet — and to 1 column `<760px`.)

| Component | Region | Purpose |
|---|---|---|
| **Role rail** | left | Persona picker (`GET /roles`), brand line, scope card, session card. Sticky. |
| **Brand card** | rail | Product name + honest tagline "grounded · cited · $0/query". |
| **Role picker** | rail | `<select>` of roles; selection drives `req.role` and the answer shape. |
| **Scope card** | rail | Read-only statement of the active role's access scope (scoped vs unrestricted). Not a control. |
| **Session card** | rail | Live per-turn `cost_usd` / `tokens` / `latency_ms`, plus `thread_id` / `user_id`, and a "Provider: invisible" line. |
| **Conversation panel** | center | Header (title + meta), scrollable stream, error-banner slot, composer, footnote. |
| **Conversation thread** | panel | Ordered user/assistant turns. (v2 renders one Q→A; see Non-goals.) |
| **User turn** | thread | The question bubble (echo of `req.query`). |
| **Assistant turn** | thread | Scope ribbon + role-adaptive answer body + evidence chips + trust strip. |
| **Answer-shape template ×3** | assistant turn | Role+`intent`-selected body: Support / Marketing / Executive (§4). |
| **Scope ribbon** | assistant turn | Inline restatement that the answer came from in-scope evidence (scoped) or all categories (unrestricted). |
| **Citation chips** | assistant turn | One chip per `citations[]` entry (`[n] label`); click → Evidence panel. |
| **Inline `[n]` markers** | answer body | In-text citation buttons; click → Evidence panel, same handler as chips. |
| **Trust strip** | assistant turn | Collapsed header (route · grounding · latency · $0) + "why ▾" expand of full `audit`. |
| **Evidence panel / bottom-sheet** | right dock | Inspect the active turn's `citations[]`: `[n]` + label + `source_id` + snippet (pending). Bottom-sheet on phone. |
| **Composer** | panel | Single text input + Send; `POST /query`. Disabled while in flight. |
| **Error banner** | panel | `400` (amber, reselect-role) vs `502` (red, retry + copy). `role="alert"`. |
| **Empty state** | panel | First-run: brand, tagline, role-conditioned starter prompts. |
| **Loading state** | panel | Skeleton + generic staged labels + Cancel. |
| **Theme toggle** | app chrome | Light/dark override on top of `prefers-color-scheme`. |

---

## 2. States per component (what drives each)

The panel is a **state machine**; one of these is active at a time (plus theme,
which is orthogonal).

| State | Trigger / driver | What renders |
|---|---|---|
| **empty** | no turns yet | Empty state with role-conditioned starters (authored copy, PRD §2 — not response data). |
| **loading** | request in flight | User turn committed + skeleton assistant turn with generic staged labels + Cancel. Composer disabled. **No audit/citations shown** (unknown until response). |
| **grounded** | `200`, `grounding.path` ∈ {`llm`,`extractive`}, `citations.length>0` | Scope ribbon + role shape body + citation chips + trust strip (collapsed header shows route/grounding/latency/$0). Default good answer. |
| **fallback (draft blocked)** | `200`, `grounding.issues` non-empty (e.g. `["llm draft blocked", ...]`), usually `path=="extractive"` | Same as grounded + a small "fallback" note on the collapsed strip; issues listed in the expanded strip. Still a grounded, cited answer. |
| **degraded-SQL** | `200`, `audit.sql_error` present | Amber warn-line; metric/trend strip **suppressed** (no `"sql"` in `sources`); RAG answer still renders + cites; `sql_error` shown in expanded strip. |
| **no-evidence** | `200`, `grounding.path=="none"`, `citations==[]` | Calm "no supporting evidence" block (not an error); trust strip shows `grounding: none`, `0 sources`. Evidence panel empty. |
| **400** | `ApiError.status==400` | Amber banner, `detail` shown, "Reselect role" action (focuses role picker). No retry. User turn preserved. |
| **502 / 500** | `ApiError.status` 502 or 500 | Red banner, `detail` (truncated) shown, "Retry" (re-POST same query+thread_id) + "Copy details". User turn preserved. |

Per-component states:
- **Trust strip:** collapsed (default, `aria-expanded=false`) ↔ expanded. Grounding
  pill variant by `grounding.path`: `llm`→"grounded (llm)", `extractive`→"grounded
  (extractive)" (partial styling), `none`→"none (unsupported)".
- **Evidence panel:** empty (no citation clicked) ↔ populated (active turn's
  `citations[]`, one item highlighted). On phone: closed ↔ bottom-sheet open.
- **Citation chip / `[n]`:** idle ↔ active (the clicked one highlights + scrolls
  its Evidence item into view).
- **Scope card / ribbon:** scoped variant vs unrestricted variant, by role.
- **Composer:** enabled ↔ disabled (in flight). Send disabled when input empty or
  no role selected.

---

## 3. Data bindings (every rendered element → exact field)

`A.x` = `audit.x`; `C[]` = `citations[]`; `R.x` = top-level response field.

| Rendered element | Exact source field | Notes |
|---|---|---|
| Answer body text | `R.answer` | Multi-line; split on `\n`, one claim per line, each ending `[n]`. Parse `[n]` into inline markers. |
| Role picker options | `GET /roles` → `roles[]` | Default-select a PRD persona; send as `req.role`. |
| Citation chip label | `C[].label` | e.g. "review B07… (Electronics)", "Returns Policy / §3", "SQL result". |
| Citation chip number / `[n]` marker | `C[].n` | Click opens Evidence for that `n`. |
| Evidence item header | `C[].n` + `C[].label` | |
| Evidence item id | `C[].source_id` | "sql" for the SQL result, else chunk id. |
| Evidence item type tag | *derived* from `C[].source_id`/`C[].label` | **Pending #3** — not a real field. |
| Evidence item snippet | — | **Pending #1** — not returned; do not fabricate. |
| Trust pill: route | `A.intent` | `sql`/`review_rag`/`docs_rag`/`sql_rag`. |
| Trust pill: grounding | `A.grounding.path` | drives label + color variant. |
| Trust pill: latency | `A.latency_ms` | |
| Trust pill: cost | `A.cost_usd` | formatted `$0.00`; green. |
| Trust fallback note | `A.grounding.issues[]` (non-empty) | shows first issue on collapsed strip. |
| Expanded: tool path | `A.tool_path[]` | join " → ". |
| Expanded: grounding explain | `A.grounding.path` | map: llm→"model-written, cite-checked"; extractive→"verbatim extract"; none→"no supporting evidence". |
| Expanded: evidence used | `A.sources[]` | count + ids. |
| Expanded: tokens | `A.tokens` | |
| Expanded: memory | `A.memory.history_turns_used`, `.persisted` | "off for this turn" when `A.memory` absent. |
| Expanded: SQL degraded | `A.sql_error` | shown only when present. |
| Expanded: grounding issues | `A.grounding.issues[]` | shown only when non-empty. |
| Session card: cost/tokens/latency | `A.cost_usd` / `A.tokens` / `A.latency_ms` | bind live per turn — no reuse across turns. |
| Session card: thread/user | `R.thread_id` / `R.user_id` | round-trip into the next `POST /query`. |
| Scope card/ribbon variant | `A.role` (or the selected role pre-response) | scoped vs unrestricted is a property of the role. |
| Scope category chips | — | **Pending #2** — names not in contract; state the fact, don't enumerate. |
| Marketing/exec chart data | `C[]` / `A.sources[]` only | render a chart **only if** `"sql"` ∈ `A.sources[]`. No second data path. |
| Error banner title/action | `ApiError.status` | 400 vs 502 routing (§2). |
| Error banner detail | `ApiError.detail` (`body.detail` from client.ts) | show verbatim (truncate 502). |

### Pending backend fields (the backend edges this rebuild may need)

The UI must not invent data (brief §5). Three signals rendered in the mockup have
**no backing field today**. Each below is marked **frontend-only** (UI can derive
or author it) or **backend change** (needs a contract edit).

1. **`citations[].snippet` — the evidence quote. (BACKEND CHANGE, recommended.)**
   `Citation` returns only `n, source_id, label`. The evidence *body* is either
   embedded inside `R.answer` (extractive path: `_extractive()` emits
   `"<label>: <quote> [n]"`) or absent (llm path). Proposed contract:
   ```
   Citation { n, source_id, label, snippet: string | null }
   ```
   `snippet` = the source text the citation points at (e.g. `hit.chunk.text`
   trimmed to ~`MAX_QUOTE_CHARS`; for `source_id=="sql"`, the `_sql_text()`
   string). It exists already inside `build_sources()` as the tuple's text half —
   it is simply not surfaced on the `Citation`. **Frontend fallback until added:**
   for the extractive path only, derive the snippet by parsing `R.answer`; for the
   llm path show label + `source_id` with no quote. Do **not** fabricate text.

2. **Scope categories per role. (BACKEND CHANGE, recommended.)**
   `A.role` gives the name; the allowed categories live in `ACCESS_POLICY`
   server-side and `GET /roles` returns names only. To enumerate the category
   chips (brief criterion 3) without duplicating governance config in the client,
   add one of:
   ```
   # option A (per-response): audit.scope = { restricted: bool, categories: string[] }
   # option B (static map):   GET /roles -> { roles: [{ name, restricted, categories[] }] }
   ```
   Prefer a response-side `audit.scope` so what's shown is exactly what retrieval
   used. **Frontend-only until added:** state *that* a scope applies (derived from
   role) and that it was applied at retrieval; do not list category names.

3. **`citations[].source_type` — evidence kind tag. (FRONTEND-ONLY; optional backend nicety.)**
   The mockup shows a "review"/"policy"/"sql" tag in the Evidence panel. It is
   **not** a field today. Derive it in the UI: `source_id=="sql"` → "sql"; label
   starting "review" → "review"; otherwise "policy/doc". Optionally the backend
   could add `source_type` to `Citation` (it already knows `chunk.source_type`),
   but the UI can ship without it.

4. **Degradation copy. (FRONTEND-ONLY — no new field; document the rule.)**
   There is no message/severity field. The UI authors the human sentences from
   field *presence*:
   - `A.sql_error` present → amber warn-line "Couldn't compute the numbers… answering from the review evidence instead"; suppress the metric/trend strip.
   - `A.grounding.path=="none"` → calm "No supporting evidence was found…"; no citations, no red banner.
   - `A.grounding.issues[]` non-empty → "fallback" note + list issues in the expanded strip.

---

## 4. Role → render rules

**Template selection = `role` + `audit.intent`.** The citation chips and trust
strip are identical across all shapes; only the answer body differs.

| Role | Typical `intent` | Body shape | Allowed to see (M6) |
|---|---|---|---|
| **support** | `review_rag` / `docs_rag` | `ISSUE` / `FIX` rows (from `R.answer` lines) + a **governing-policy card** quoting the doc citation (`C[]` whose `source_id` is a doc / label is a policy). | **Scoped** — a subset of categories (enforced server-side). |
| **marketing** | `sql_rag` | Theme bars + a **sentiment trend** strip labelled "from SQL"; rendered only if `"sql"` ∈ `A.sources[]`. | **Scoped** — a different category subset. |
| **executive** | `sql_rag` | Headline line + **ranked-metric bars** + a one-line cause; metric rendered only if `"sql"` ∈ `A.sources[]`. | **Unrestricted** — all categories. |
| admin / analyst | any | Default shape (plain claim lines + chips + strip). | Unrestricted; not PRD drivers. |

Rules the build must honor:
- **Scope is enforced server-side; the UI never widens it.** No control, toggle,
  or query param that could request out-of-scope data. The scope card/ribbon is
  read-only (decision D-07).
- **Charts read only what the response carried.** A metric/trend strip is a view
  of the same M6-scoped retrieval (`C[]` / `A.sources`). If `"sql"` is absent
  (e.g. `sql_error`), suppress the chart — never fabricate or fetch a second,
  unscoped dataset (decision D-05).
- **Shape is presentation only.** All three render the *same* grounded, cited
  `R.answer`; switching persona must not change what evidence exists, only its
  layout.
- If `role`/`intent` don't match a known template, fall back to the default shape
  (plain claim lines) — never error.

---

## 5. Accessibility contract

| Requirement | Where it applies |
|---|---|
| **`:focus-visible` ring** (2px accent, 2px offset) | every interactive element: role select, starters, chips, `[n]` markers, trust header, composer, banner buttons, theme toggle, sheet close. |
| **`aria-expanded`** reflecting open/closed | trust-strip "why" header (toggles true/false); pending-fields toggle. |
| **`aria-live="polite"`** on the stream | so a landed answer is announced. (No stream transport — it announces once the response renders.) |
| **`role="alert"`** on error banners | 400 and 502 banners announce immediately. |
| **`aria-label` on every chart/visual** | theme bars, trend sparkline (`<svg role="img" aria-label="…">`), ranked bars — label states the data in words (e.g. "Sentiment trend rising from 3.4 to 3.9 stars"). Charts are decorative-plus-labelled, never the only carrier of a fact (the answer text carries it too). |
| **`prefers-reduced-motion`** respected | disable skeleton shimmer and any transition for reduced-motion users. |
| **Theme contrast** | both light and dark token sets meet WCAG AA for text on surface; the two schemes are defined as token overrides (`prefers-color-scheme` + explicit `data-theme`). |
| **Keyboard paths** | Enter submits the composer; all actions reachable by Tab in reading order; citation `[n]` and chips are real `<button>`s (not spans); Escape closes the bottom sheet. |
| **Bottom-sheet focus handling** | opening the sheet moves focus into it and the close control is reachable; closing returns focus to the triggering chip; backdrop click closes. |
| **16px gutter / no horizontal scroll** | enforced at phone width; columns stack (rail → top bar, Evidence → bottom sheet, composer pinned). Long labels/ids ellipsize or wrap — never force horizontal scroll. |
| **Citation markers labelled** | each `[n]` has `aria-label="Show evidence n"`; chips expose the label text. |

---

## 6. Non-goals for this build (carried from `02_decisions.md` §2)

- **No streaming.** Backend returns once; loading is a generic staged simulation
  (D-12). Do not build a token stream.
- **No authentication.** Role is a self-selected persona picker; `user_id` is a
  local anonymous id (reuse v1's `localStorage` approach). No login/trust boundary.
- **No multi-turn history / conversation list.** Render a single Q→A turn; memory
  is *reported* via `A.memory`, not rendered as a history (D-15). Keep the
  `thread_id`/`user_id` round-trip plumbing correct for a future pass.
- **Do not enumerate scope categories** until Pending #2 ships; state the fact only.
- **Do not change the backend pipeline** beyond (optionally) the Pending #1/#2
  contract additions, which must be specced separately before implementation.

---

*Sources of truth: `backend/app/main.py`, `backend/agents/pipeline.py`,
`backend/agents/composer.py` (verified fields), `docs/design/00_brief.md`,
`01_wireframes.md`, `02_decisions.md`, `mockups/m8-chat.html` (approved D2). v1
surface being replaced: `frontend/src/{App.tsx, components/*, api/*}`.*
