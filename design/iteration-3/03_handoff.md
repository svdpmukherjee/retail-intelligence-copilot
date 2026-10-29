# 03 · Build Handoff — M8 Chat / Serving UI (v3)

**Design Track · iteration 3 · Stage 5 (build spec).** The Developer implements
the M8 **v3** conversation layer from *this* document. It is a **delta** on the
iteration-2 handoff (`design/iteration-2/03_handoff.md`), which the v3 build still
follows for everything not named here. Iteration 2's **§0 contract, §1 component
inventory, §2 state machine, §3 data bindings, §4 role→render, §5 a11y, §6
non-goals carry forward unchanged by reference.** This spec adds only the
conversation shell (identity switcher, history rail, stacked turns, one-at-a-time
evidence) and the **one** backend edge iteration 3 introduces.

> **Scope of the rebuild.** Iteration-2 (M8 v2) already shipped the trust strip,
> three role shapes, state machine, scope/cost surface, theme tokens, and the
> `api/` layer. v3 wraps a conversation shell around that working surface. **Do
> not change the backend pipeline.** The only backend work is one read-only
> endpoint + one `MemoryStore` read method (§1), and one *optional/pending* persist
> change for full-fidelity resume (§2) — both called out explicitly.

---

## 0. Contract delta (what iteration 3 binds to beyond iteration-2 §0)

Verified against `backend/`. Iteration-2 §0 still describes `POST /query`,
`Citation`, `audit`, and errors. Two fields iteration 2 listed as **Pending are
now REAL** and bind directly:

```
audit.scope   = { restricted: bool, categories: string[] }     # pipeline.py ~L104
                # restricted = bool(categories); categories = decision.scope["category"]
citations[].snippet : string | null                            # composer.py _snippet()
                # redact(" ".join(text.split())[:MAX_QUOTE_CHARS]); MAX_QUOTE_CHARS = 240
                # PII-redacted AT SOURCE — the UI shows it verbatim, never un-redacts
```

`POST /query` request/response (unchanged, re-stated for the round-trip that
drives ownership + continuity):
```
request : { query, role, thread_id?: string|null, user_id?: string|null }   # QueryRequest
response: AnswerResult + { thread_id: string|null, user_id: string|null }    # QueryResponse
```
`user_id` is the **owner key** iteration 3 leans on; `thread_id` is continuity.
When `req.user_id` is set and `thread_id` is null, `main.py` already creates a
thread (`new_thread(user_id, role)` → `MemoryStore.create_thread`). No change.

**New in iteration 3:** `GET /threads` (§1) and, for resume, a thread-detail read
(§2).

---

## 1. The one backend edge, specced — `GET /threads`

A read-only endpoint that lists the active identity's threads to populate the
left-rail history list (brief §6, wireframe §0 ⚑ HANDOFF #1). **One new route +
one new `MemoryStore` method.**

### Request
```
GET /threads?user_id=<id>&role=<role>
```
- The owner is identified by the **`user_id` the client already round-trips** on
  `POST /query`. Since this is a `GET`, it travels as a query param (mirrors the
  body `user_id` on `POST /query`). `role` is the active identity's role.
- **This is a *demo* identity, not an authenticated principal (D-16).** The
  endpoint MUST therefore owner-filter **server-side** by `user_id` and never
  trust a client-supplied thread list — the exact same guard shape as
  `MemoryStore.append_message` / `recent_messages`, which scope every read/write
  by `WHERE ... user_id = %s`.

### Response
```json
{ "threads": [ { "id": "…", "label": "…", "created_at": "2026-10-29T…Z", "turn_count": 4 } ] }
```
| Field | Source | Notes |
|---|---|---|
| `id` | `threads.id` | click → resume (§2); round-trips back as `thread_id`. |
| `label` | **derived server-side** | first *user* message of the thread: `messages.content` where `role_kind='user'` at `min(turn)`, truncated (~48 chars). **Already PII-redacted** — `MemoryManager.persist` writes user turns through `_redact` (`append_message(..., self._redact(query), ...)`). ⚑ **Label-derivation is a decision, not a column:** `threads`/`messages` have **no `label` column** (see `schema.py`: `THREAD_COLUMNS`, `MESSAGE_COLUMNS`). Derive it in the `list_threads` query; do **not** invent a column. |
| `created_at` | `threads.created_at` | for the relative timestamp ("2h ago"). |
| `turn_count` | derived | `COUNT(*)` of that thread's `messages` (or `/2` for Q+A pairs) — illustrative count for the row; keep it a simple aggregate. |

### Governance — what "owner-filtered AND M6-scope-aware" means for a list
- **Owner-filtered:** `WHERE threads.user_id = :user_id`. `support_1` must never
  receive `support_2`'s rows. This is the observable proof of brief §4 criterion 1.
- **Scope-aware (list form):** also `AND threads.role = :role`. A thread is owned
  by a `(user_id, role)` pair (`threads` has both columns). Filtering by the
  active role ensures the rail never surfaces threads created under a *different*
  role (and therefore a different M6 scope) even if a future `user_id` holds more
  than one role. The list endpoint returns **no turn content and no snippets** —
  only id/label/created_at/turn_count — so there is no path for out-of-scope
  *evidence* to leak through the list itself; content governance is enforced at
  resume (§2) and at query time by the unchanged pipeline.

### New store method (does not exist yet)
The M5 tables exist (`threads`, `messages` in `schema.py`); the list query does
not. `MemoryStore` has `create_thread`, `append_message`, `recent_messages`,
`list_memory`, `trim_memory` — but **no `list_threads`**. Add:
```python
def list_threads(self, user_id: str, role: str) -> list[ThreadListRow]: ...
#   SELECT t.id, t.created_at,
#          (first user message content) AS label,
#          COUNT(m.id) AS turn_count
#   FROM threads t LEFT JOIN messages m ON m.thread_id = t.id
#   WHERE t.user_id = %s AND t.role = %s
#   GROUP BY t.id ORDER BY t.created_at DESC
```
Parameterised and user-scoped, consistent with the rest of the store. This is the
developer's **one new store method + one new FastAPI route**; no schema change.

---

## 2. Resume-payload mechanism — DECISION (not left open)

**Goal:** clicking a history row restores *all* that thread's prior turns into the
stacked center (wireframe §4). The question is where each restored turn's text —
and its `audit` + `citations` — come from.

**What M5 persists today (verified):** `messages` stores **redacted `content`
only** — `MessageRow` = `id, thread_id, turn, role_kind, content, created_at`
(`schema.py`). `MemoryManager.persist` appends the user query and the assistant
answer, both through `_redact`. **It does NOT store `audit` or `citations`.** So
audit/citations for an old turn are simply **not available to read back**.

### Options
| | Mechanism | Verdict |
|---|---|---|
| (a) | **Thread-detail read** `GET /threads/{id}` returning the stored turns (ordered `messages`: `turn`, `role_kind`, `content`). | **ADOPT as the minimum.** Returns exactly what was persisted; owner-checked like `recent_messages(user_id=…)`. |
| (b) | **Re-run `POST /query` per restored turn** to rebuild audit/citations. | **REJECTED (D-21).** Recomputes, costs tokens/latency, and can yield a *different* answer — it misrepresents "what actually happened." |
| (c) | **Persist each assistant turn's `audit` + `citations`** at answer time, read back via (a). | **PENDING backend change** — the only honest route to full-fidelity restored turns (trust strip + evidence on old turns). |

### Decision for the reference build
**Ship (a) now; flag (c) as a pending backend change.** Concretely:

- **`GET /threads/{id}?user_id=<id>`** → `{ thread_id, role, turns: [{ turn, role_kind, content }] }`,
  owner-checked server-side (reuse the `recent_messages(..., user_id=…)` owner
  guard; unknown/non-owned thread → empty/`404`, never another owner's data).
- **Restored assistant turns render the stored answer text** in the role shape
  (§3), **but carry a muted "historical turn — reasoning & evidence not stored
  for replay" note instead of a live trust strip / clickable evidence.** Do **not**
  fabricate an `audit` or `citations` for a restored turn — there is no field to
  bind them to. (The v3 *mockup* shows full strips on restored turns as a flagged
  canned convenience; the build must not, until (c) lands — D-21.)
- **Live turns in the same thread** (asked this session) keep their full trust
  strip + one-at-a-time evidence from the in-memory `QueryResponse` — unchanged
  from iteration 2.
- **Pending (c), to spec separately before implementing:** persist per
  assistant-turn `audit` (dict) + `citations` (list) — e.g. an `assistant_meta`
  JSONB column on `messages`, or a sibling table keyed by `(thread_id, turn)` —
  written in `MemoryManager.persist`, returned by `GET /threads/{id}`. Then
  restored turns become fully inspectable like live ones and the muted note is
  dropped. **This is a schema add; it is not in scope for the v3 UI build** — the
  UI must degrade honestly without it.

---

## 3. New components, states, bindings (delta on iteration-2 §1–§3)

Inherited components (brand card, role/answer shapes, scope ribbon, trust strip,
citation chips/`[n]`, composer, error banner, empty/loading states, theme toggle)
are **unchanged — see iteration-2 §1**. New or changed:

| Component | Region | Purpose | States | Binds to |
|---|---|---|---|---|
| **Identity switcher** (D-16) | rail top | `<select>` of demo identities (`support_1/2`, `marketing_1`, `executive_1`); labelled "demo — not a login". Shows active role + user. | idle; on change → switch flow | selected value → `user_id` (owner key, sent on `POST /query` + `GET /threads`); its role → `req.role`. |
| **History list + "+ new chat"** (D-17) | rail | Owner-scoped thread list; "+ new chat" clears center to empty. | **populated** (rows); **empty** ("No conversations yet…"); **row active** (exactly one, `aria-current`). | `GET /threads` → rows (`id`/`label`/`created_at`/`turn_count`). Owner-scoped by `user_id`+`role` (§1). |
| **History row** | history list | One past thread. | idle; hover; **active**. | `T.label` (text), `T.created_at` (relative time); click → resume with `T.id`. |
| **Stacked-turn container** (D-18) | center | Scrollable vertical stack of ALL active-thread turns; composer pinned; follow-up appends. | empty (new chat); 1..N turns; in-flight (skeleton as newest turn, earlier turns stay). | each turn: user bubble = `req.query`/stored `content`; assistant = role shape over `R.answer`/stored `content`. |
| **One-at-a-time Evidence panel** (D-19) | right dock / bottom sheet | Inspect exactly ONE citation. | **empty** (default prompt); **one shown**; **replaced** on a different `[n]`. Phone: closed ↔ bottom sheet. | `citations[].n` / `.label` / `.source_id` / `.snippet`; type tag *derived* from `source_id`/`label` (iteration-2 Pending #3, unchanged). |
| **Phone history drawer** | phone only | `☰` opens history off-canvas; identity stays in the top control. | closed ↔ open (+ backdrop). | same `GET /threads` data. |

### Switch / new-chat / resume behaviours (the flows)
- **Switch identity** → reload the rail to the new owner's `GET /threads`; **reset
  the center to the new-chat empty state** owned by the new identity (nothing from
  the prior owner lingers — brief §4 criterion 7); scope card re-derives from the
  new role's `audit.scope` (next query) / `scope_for_role` mapping meanwhile.
- **"+ new chat"** → center = empty state (inherited iteration-2 §2, now owned by
  the active identity); no row active. The thread **does not appear in the rail
  until its first answer persists**; on the `QueryResponse` landing (`thread_id`
  now set), **re-fetch `GET /threads`** → the new row appears and becomes active.
- **Resume** (row click) → `GET /threads/{id}` (§2) → stack restored turns
  oldest→newest; row goes active (`aria-current="true"`); a follow-up posts with
  the resumed `thread_id`.

### Data bindings (new rows; iteration-2 §3 table otherwise holds)
| Rendered element | Exact field | Notes |
|---|---|---|
| History row label | `GET /threads` → `threads[].label` | derived server-side from first user `messages.content` (redacted); **not a column** (§1). |
| History row time | `threads[].created_at` | rendered relative. |
| History row count | `threads[].turn_count` | derived aggregate. |
| Active identity → owner | selected `user_id` | sent as `req.user_id` + `GET /threads?user_id=`. |
| Scope chips (rail + ribbon) | `audit.scope.categories` / `.restricted` | **now a real field (D-20)** — enumerate chips from it; never hard-code; `restricted:false` → unrestricted note. |
| Evidence snippet | `citations[].snippet` | **now a real field (D-20)**; PII-redacted at source; show verbatim; `null` → "snippet unavailable", never fabricated. |
| Restored turn text | `GET /threads/{id}` → `turns[].content` | stored redacted text; assistant turns get the muted "historical turn" note (§2) — **no** audit/citations bound. |
| Continuity | `R.thread_id` round-trip | follow-ups post the active `thread_id`. |

---

## 4. Role → render (inherited)

**Unchanged from iteration-2 handoff §4** (template = `role` + `audit.intent`;
charts gated on `"sql" ∈ audit.sources[]`; scope never widened client-side). The
**only** change: the three role shapes now render **inside the stacked multi-turn
container** (D-18), once per assistant turn, rather than as a single Q→A. Shape
selection, chart gating, and the "shape is presentation only" rule are identical.

---

## 5. Accessibility (delta on iteration-2 §5)

Iteration-2 §5 holds in full (focus-visible rings, `aria-expanded` on the trust
strip, `aria-live` on the stream, chart `aria-label`s, `prefers-reduced-motion`,
16px gutter / no h-scroll, labelled `[n]` markers). **Add for the new controls:**

| Requirement | Where |
|---|---|
| Identity switcher labelled | the `<select>` has an accessible name ("Demo identity"); its demo-not-a-login status is textually present, not colour-only. |
| History rows are real `<button>`s | keyboard-reachable; the active row carries **`aria-current="true"`**; label text is the accessible name. |
| "+ new chat" labelled | real `<button>` with a clear name; reachable in Tab order at the top of the list. |
| Phone history drawer | opening moves focus into the drawer; **Escape closes** it and returns focus to the `☰` toggle; backdrop click closes; `aria-expanded` on the toggle. Mirrors the inherited bottom-sheet focus rules. |
| One-citation replace keeps focus sane | clicking a new `[n]` updates the (single) Evidence item in place; focus stays on the clicked marker; the previously-active marker de-highlights (no focus trap, no scroll jump). |
| `aria-live` on the stream across turns | a newly-appended turn is announced once rendered (no stream transport — inherited D-12). |

---

## 6. Non-goals (carried from iteration-2 §6 + iteration-3 D-17/D-21)

- **No streaming** (inherited; PRD §5, D-12).
- **No authentication** — the identity switcher is a *demo* owner selector (D-16);
  `GET /threads` still owner-filters server-side and never trusts a client list.
- **No thread rename / search / delete** (D-17); list + resume + new only.
- **No full-fidelity resume of audit/citations** until the pending persist change
  (D-21 / §2 option c) ships; restored turns show stored text + a muted
  "historical turn" note and do **not** fabricate a trust strip or evidence.
- **Do not change the backend pipeline.** The only backend work is `GET /threads`
  + `GET /threads/{id}` (read-only) and `MemoryStore.list_threads` (§1–§2); the
  per-turn audit/citations persist (§2 c) is a *separate* schema change to spec
  before implementing.

---

*Sources of truth: `backend/app/main.py` (`POST /query`, `GET /roles`),
`agents/pipeline.py` (`audit.scope` ~L104), `agents/composer.py`
(`Citation.snippet`, `_snippet`, `MAX_QUOTE_CHARS`), `memory/store.py`
(`MemoryStore` — no `list_threads` yet; `append_message`/`recent_messages` owner
guard), `memory/schema.py` (`threads`/`messages` columns — no `label`, no
audit/citations persisted), `memory/manager.py` (`persist`/`_redact`). Design:
`i3/00_brief.md`, `i3/01_wireframes.md`, `i3/02_decisions.md`,
`i3/mockups/m8-chat-v3.html` (approved D2). Inherited spec:
`design/iteration-2/03_handoff.md` (iteration-2 §0–§6).*
