# 01 · Wireframes — M8 Chat / Serving UI · **iteration 3**

**Design Track · iteration 3 · Stage D2-prep (lo-fi).** Annotated box layouts
only — no color, type, or polish; the hi-fi mockup is the next stage. This is a
**delta** on iteration-2 `01_wireframes.md`: it draws **only** what iteration 3
adds or changes (the four brief §3 additions — A identity switcher, B history
rail + new chat, C stacked turns, D click-to-inspect ONE citation) and their
states. Everything else — the trust strip (D-02, collapsed by default), role
shapes (§5a–c), the Evidence snippet/label/source_id card, the empty / loading
/ grounded / scope / degradation / error states, the responsive collapse rules
(236px | 1fr | 300px → 2col `<1080` → 1col `<760`, Evidence → bottom sheet) — is
**inherited unchanged** and referenced by iteration-2 section number, not
re-drawn.

Field legend (same as iteration 2): `A.x` = `audit.x`; `C[]` = `citations[]`;
`R.x` = top-level response field. New in iteration 3: `T[]` = a thread row from
`GET /threads`; `ID` = the active demo identity (role + user-within-role).

---

## 0. Field → source map — iteration-3 additions only

(Iteration-2 §0 map still holds for `R.answer`, `C[]`, `A.*`, `R.thread_id`,
`R.user_id`. These rows are what iteration 3 newly binds to.)

| UI signal | Real field | Notes |
|---|---|---|
| Active identity (role + user) | `ID.role` + `ID.user_id` | demo switcher value; `user_id` is sent as `R.user_id` and is the **owner key** |
| History row label | `T[].first_question` (derived) | short label = first user message of the thread ⚑ HANDOFF (derivation/field TBD) |
| History row timestamp | `T[].created_at` | from `threads.created_at` |
| History row thread id | `T[].id` | click → resume; matches `threads.id` |
| Owner of a thread | `threads.user_id` | **governance:** list filtered to `ID.user_id` ⚑ |
| Restored turn text | `messages.content` (per `turn`) | ordered by `threads`→`messages.turn`, oldest→newest |
| Restored turn audit/citations | ⚑ HANDOFF — mechanism undecided | see §8: re-fetch per turn vs. thread-detail read returning them |
| Scope chips (unchanged) | `A.scope = { restricted, categories }` | enumerated from `audit.scope` only, never hard-coded |
| Inspected snippet (unchanged) | `C[].snippet` (PII-redacted, may be null) | shown as-returned; null → "snippet unavailable" note, never fabricated |

### ⚑ HANDOFF items this stage raises (carry to `03_handoff.md`)

1. **`GET /threads` must be owner + M6-scope filtered.** The rail lists only
   `ID.user_id`'s threads, and never a thread/turn/snippet outside the active
   role's M6 scope. This is the single backend edge iteration 3 introduces
   (brief §6) — request/response shape is a handoff decision, not invented here.
2. **Resume payload — where do restored turns' audit + citations come from?**
   The wireframe shows resumed turns with working trust strips + evidence *as if*
   `A.*`/`C[]` are available per turn. The **mechanism** is undecided: does
   `GET /threads` (or a thread-detail read) return each turn's audit/citations,
   or does the client re-fetch per turn? Flagged, not solved. Do not invent a
   contract.
3. **History row label derivation.** `messages` stores `content`; a short row
   label (first question, truncated) must be derived or returned as a field.

---

## 1. Overall layout — the conversation shell (what changed vs. iteration-2 §1)

Same three-region shell and the **same** region widths/breakpoints as
iteration-2 §1 (236px | 1fr | 300px). Iteration 3 changes the **contents** of
two regions and refines the third:

- **LEFT RAIL** gains, top to bottom: (A) a **demo identity switcher**, then
  (B) a **"+ new chat"** control + an **owner-scoped history list**. The
  iteration-2 scope line + session block stay below, unchanged.
- **CENTER** (C) now **stacks ALL turns** of the active thread (oldest→newest,
  newest at bottom), scrollable, composer pinned below — replacing iteration-2's
  single Q→A render.
- **RIGHT / EVIDENCE** (D) becomes strictly **one-citation-at-a-time**: default
  empty prompt; a clicked `[n]`/chip from *any* turn shows exactly one citation;
  a different click **replaces** it.

```
┌────────────────────┬──────────────────────────────────┬───────────────┐
│  LEFT RAIL (236)   │     CONVERSATION (1fr, scrolls)   │ EVIDENCE (300)│
│                    │                                   │               │
│ ┌ DEMO IDENTITY ─┐ │  ┌ user turn (t-2) ───────────┐  │  (empty by    │
│ │ ⚙ demo · not   │ │  │ "Top complaints Beauty?"   │  │   default)    │
│ │   a login      │ │  └────────────────────────────┘  │               │
│ │ role: marketing│ │  ┌ assistant turn (t-2) ──────┐  │  "Click a     │
│ │ user: mktg_1 ▾ │ │  │ …answer… [1][2]            │  │   citation    │
│ └────────────────┘ │  │ ┌ trust strip (collapsed) ┐│  │   [n] in any  │
│ ┌──────────────┐   │  │ └──────────────────────────┘│  │   turn to     │
│ │  + new chat  │   │  └────────────────────────────┘  │  inspect it   │
│ └──────────────┘   │  ┌ user turn (t-1) ───────────┐  │  here."       │
│ HISTORY (yours):   │  │ "…and why for Beauty?"     │  │               │
│ ┌────────────────┐ │  └────────────────────────────┘  │  (shows ONE   │
│ │● Top complaints│ │  ┌ assistant turn (t-1) ──────┐  │   C[] on      │
│ │  Beauty  2h ago│ │  │ …answer… [1]              │  │   click;      │
│ ├────────────────┤ │  │ ┌ trust strip (collapsed) ┐│  │   replaces,   │
│ │  Returns copy  │ │  │ └──────────────────────────┘│  │   never       │
│ │  yesterday     │ │  └────────────────────────────┘  │   stacks)     │
│ └────────────────┘ │           … scrolls …            │               │
│ ── scope ──  (i2§6)│  ┌ composer (pinned) ─────────┐  │               │
│ ── session ─ (i2§1)│  │ [ ask a question…  ](send) │  │               │
└────────────────────┴──└────────────────────────────┘──┴───────────────┘
            ⚑ history list owner-scoped by ID.user_id (GET /threads)
```

**Why this placement (justification).** Identity sits **above** history because
it is the *owner* of everything below it — switching it re-scopes the whole rail,
so it reads as the root of the left column, not a buried setting. History sits in
the left rail (not the center) so the active conversation keeps the full center
width and resuming is a lateral move, not a modal. "+ new chat" sits at the top
of the list (the conventional, reach-for-it-first position). The Evidence dock
stays on the right exactly as iteration-2 D-01, but is now *scoped to one* so a
long multi-turn thread can't flood it with every turn's evidence (brief §3 D).
The iteration-2 scope + session blocks stay at the rail's foot — they describe
the *active answer's* governance, below the navigation that chooses it.

---

## A. Identity switcher — the demo control (brief §3 A)

A labelled **demo** control at the top of the rail. It is explicitly *not* a
login (no password, no avatar-as-auth); the label says so. Shows the active
role and the user-within-role; the dropdown lists the demo identities of
brief §2 (`support_1`, `support_2`, `marketing_1`, `executive_1`).

```
┌ DEMO IDENTITY ───────────────────┐
│ ⚙ demo identity — not a login    │ ← fixed label (brief §2/§5: this is a
│                                   │   reviewer affordance, not auth)
│ role   : marketing                │ ← ID.role  (drives A.role on next query)
│ user   : [ marketing_1        ▾ ] │ ← ID.user_id  (the OWNER key; sent as
│          ┌──────────────────────┐ │   R.user_id). Dropdown options:
│          │ support_1            │ │     support_1 · support_2
│          │ support_2            │ │     marketing_1 · executive_1
│          │● marketing_1         │ │   (role shown beside each)
│          │ executive_1 (unrestr)│ │
│          └──────────────────────┘ │
└───────────────────────────────────┘
```

Notes:
- Selecting a **different** identity triggers the switch flow (§3d): rail
  reloads to the new owner's `GET /threads`; center resets to the **new-chat
  empty state** (the sensible default — nothing from the prior identity lingers).
- ⚑ The chosen `user_id` is the governance owner key: `GET /threads` and every
  `POST /query` carry it; the rail must *only* ever show this owner's threads.

---

## B. History list + "+ new chat" (brief §3 B)

### State (a) — identity with several threads

```
┌──────────────┐
│ + new chat   │ ← starts a fresh empty thread (§5), owned by ID
├──────────────┤
│ HISTORY (yours)             ⚑ owner-scoped to ID.user_id
│ ┌──────────────────────────┐
│ │● Top complaints Beauty   │ ← active/selected row: filled marker ●,
│ │  2h ago                  │   label = T[].first_question (derived ⚑),
│ ├──────────────────────────┤   timestamp = T[].created_at
│ │  Returns policy wording  │
│ │  yesterday               │ ← inactive row: hollow/no marker
│ ├──────────────────────────┤
│ │  Earbud fit complaints   │
│ │  Mon                     │
│ └──────────────────────────┘
└──────────────┘
   click a row → resume that thread (§4)
```

### State (b) — identity with zero threads (new owner)

```
┌──────────────┐
│ + new chat   │
├──────────────┤
│ HISTORY (yours)
│  ┌────────────────────────┐
│  │ No conversations yet.  │ ← GET /threads returned [] for this owner
│  │ Start one with         │   (e.g. just switched to support_2)
│  │ “+ new chat” above.    │   NOT an error — an empty, owned list
│  └────────────────────────┘
└──────────────┘
```

### State (c) — active/selected thread highlighted

The resumed/active thread's row carries the filled `●` marker + emphasized box
(lo-fi: double border) so "which conversation am I in" is unambiguous. Exactly
one row is active at a time. A brand-new unsaved chat → **no** row active yet
(the thread doesn't exist in the rail until its first answer persists, §5).

Notes:
- Rows are **resume-only** — no rename, search, or delete affordance anywhere
  (brief §5 non-goals / BACKLOG). Lo-fi draws no hover menu, no kebab.
- ⚑ The list is owner-scoped: switching `support_1`→`support_2` must yield a
  *different* set (or empty), never the union — this is the observable proof of
  owner-scoping (brief §4 criterion 1).

---

## 3d. Just-switched-identity state (rail reloaded, center reset)

What the screen shows the instant a *different* identity is picked:

```
LEFT RAIL                         CENTER
┌──────────────────┐              ┌───────────────────────────────┐
│ role : support   │              │   (new-chat empty state —      │
│ user : support_2 │              │    reuse iteration-2 §2)       │
├──────────────────┤              │                               │
│ + new chat       │              │   Retail Intelligence Copilot  │
├──────────────────┤              │   starter prompts for support  │
│ HISTORY (yours)  │              │   (persona-conditioned, i2 §2) │
│  No conversations│ ← reloaded   │                               │
│  yet.            │   to new     │   [ composer, empty ]          │
│                  │   owner's    │                               │
└──────────────────┘   GET/threads└───────────────────────────────┘
```

- **Call-out:** right after a switch the **center resets to the new-chat empty
  state** (iteration-2 §2), owned by the newly-selected identity. Nothing from
  the previous identity's thread remains on screen — this prevents one owner's
  conversation bleeding into another's view (brief §4 criterion 7). Starter
  prompts re-condition to the new role (iteration-2 §2 behaviour, inherited).
- The rail history simultaneously reloads to the new owner's `GET /threads`
  (here: empty, if `support_2` has no threads).

---

## 4. Resume flow — click a thread → load ALL its turns (brief §3 B + C)

Clicking a history row loads **every** prior turn of that thread into the
center, oldest→newest, trust strip + evidence working on each (criterion 2).

```
(row “Top complaints Beauty” clicked → that row goes active ●)

CENTER — restored thread, 3 turns, scrolled to show turns 1→2:
┌───────────────────────────────────────────────────────────┐
│ ┌ user · turn 1 ──────────────────────────────┐            │
│ │ "Top complaints about Beauty this quarter?"  │           │ ← messages.content
│ └──────────────────────────────────────────────┘           │   (role_kind=user, turn 1)
│ ┌ assistant · turn 1 ─────────────────────────┐            │
│ │ Top complaints: fragrance, packaging… [1][2] │           │ ← restored R.answer
│ │ [1 review…] [2 review…]                      │           │ ← restored C[]  ⚑(mech)
│ │ ┌ trust strip (collapsed) ────────────────┐ │           │ ← restored A.*  ⚑(mech)
│ │ │ ⟐ sql_rag · ⛨ grounded · 380ms · $0 ▾ │ │           │   collapsed (D-02)
│ │ └──────────────────────────────────────────┘ │           │
│ └──────────────────────────────────────────────┘           │
│ ┌ user · turn 2 ──────────────────────────────┐            │
│ │ "…and why for fragrance specifically?"       │           │ ← follow-up, turn 2
│ └──────────────────────────────────────────────┘           │
│ ┌ assistant · turn 2 ─────────────────────────┐            │
│ │ Fragrance complaints cluster on longevity[1] │           │
│ │ [1 review…]   ⟐ sql_rag · ⛨ grounded ▾     │           │
│ └──────────────────────────────────────────────┘           │
│                      … turn 3 below the fold …             │
│ ┌ composer (pinned) ───────────────────────────┐           │
│ │ [ ask a follow-up…                   ](send) │           │ ← posts into SAME thread
│ └───────────────────────────────────────────────┘           │   (R.thread_id = T[].id)
└───────────────────────────────────────────────────────────┘
```

Notes:
- Restored turns are **visually identical** to live turns (same role shape §5,
  same collapsed trust strip, same clickable `[n]`). A reviewer can expand the
  strip or inspect a citation on an *old* turn exactly as on a fresh one.
- ⚑ HANDOFF #2: the wireframe assumes each restored turn's `A.*` + `C[]` are
  available. Whether they arrive via `GET /threads`, a thread-detail read, or a
  per-turn re-fetch is **undecided** — a handoff decision, not drawn here.
- A follow-up typed into the pinned composer **appends** below turn 3 (§C /
  stacking), posting with the resumed `thread_id`.

---

## 5. New-chat flow — "+ new chat" → empty → first answer creates the thread

```
STEP 1: click "+ new chat"          STEP 2: ask & answer         STEP 3: rail refresh
┌ RAIL ──────┐  ┌ CENTER ─────┐     ┌ CENTER ─────────┐          ┌ RAIL ──────────┐
│ + new chat │  │ (empty state│     │ user: "…?"      │          │ + new chat     │
│ HISTORY    │  │  iter-2 §2, │     │ assistant: …[1] │          │ HISTORY        │
│  (no row   │  │  owned by   │ --> │  trust strip ▾  │   -->    │ ┌────────────┐ │
│  active)   │  │  active ID) │     │                 │          │ │● <new row> │ │ ← NOW appears:
│            │  │ [composer]  │     │ [composer]      │          │ │  just now  │ │   thread persisted,
└────────────┘  └─────────────┘     └─────────────────┘          │ └────────────┘ │   GET /threads
                                                                  └────────────────┘   re-fetched
```

- The new thread **does not appear in the rail until its first answer persists**
  (criterion 3). On the response landing, `R.thread_id` exists → rail re-fetches
  `GET /threads` → the new row appears and becomes the active `●` row.
- **Call-out (rail-refresh moment):** the single moment the history list mutates
  on its own is *right after the first answer of a new chat* — draw it as the new
  top row sliding in, newly active. No optimistic row before persistence (nothing
  to show / could mislead if the query errors).
- The empty state itself is **reused verbatim** from iteration-2 §2 (starter
  prompts, headline) — not redrawn here; only its *ownership* (by active ID) is
  new.

---

## C (detail). Stacked multi-turn thread — scroll & pinning (brief §3 C)

Replaces iteration-2's single Q→A center. Turns stack oldest→newest; newest at
bottom; the composer is pinned below the scroll region.

```
┌ CONVERSATION (scroll region) ───────────────────────────┐
│ ▲ older turns scroll up out of view                     │
│ ┌ user t-1 ─────────────┐                               │
│ │ "…"                   │                               │
│ └───────────────────────┘                               │
│ ┌ assistant t-1 ────────┐                               │
│ │ …[1]  ⟐ · ⛨ · $0 ▾  │ ← trust strip COLLAPSED        │
│ └───────────────────────┘   (all turns, inherited D-02) │
│ ┌ user t (newest) ──────┐                               │
│ │ "follow-up…"          │                               │
│ └───────────────────────┘                               │
│ ┌ assistant t (newest) ─┐                               │
│ │ …[1][2]  ⟐ · ⛨ ▾    │ ← newest, auto-scrolled to    │
│ └───────────────────────┘   bottom on arrival          │
├─────────────────────────────────────────────────────────┤
│ ┌ composer (PINNED, always visible) ──────────────────┐ │
│ │ [ ask a follow-up…                        ](send)   │ │
│ └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

Notes:
- **All trust strips default collapsed** (inherited D-02) — including on
  restored turns — so a long thread stays scannable; each expands independently
  on its own `[why ▾]`.
- A follow-up **appends** below (never replaces) the prior turn (criterion 4);
  on the new answer landing the view auto-scrolls so the newest turn is in view,
  composer still pinned.
- While a follow-up is in flight, the pending assistant skeleton (iteration-2
  §3, inherited) renders as the newest stacked turn; earlier turns stay visible.

---

## D (detail). Evidence panel — click-to-inspect ONE citation (brief §3 D)

The right dock is now strictly single-citation. Two states.

### D-empty — default / nothing inspected
```
┌ EVIDENCE ─────────────────────┐
│ (empty)                       │
│  Click a citation [n] in any  │ ← prompt copy (authored, not a field)
│  turn to inspect its source   │
│  here.                        │
└───────────────────────────────┘
```

### D-one — exactly one citation shown (any turn's [n] clicked)
```
Thread: turn t-2 has [1][2]; turn t has [1][2][3].
User clicks [2] on turn t-2  →

┌ EVIDENCE ─────────────────────┐        turn t-2:  …[1]·[2*]…   ← [2] now ACTIVE
│ ● [2]  review B0ABC (Beauty)  │ ← C[].n + C[].label   (highlighted in the turn)
│   source_id: B0ABC#3          │ ← C[].source_id
│   type: review                │ ← derived tag from source_id/label (not un-redacted)
│   ┌─────────────────────────┐ │
│   │ "…scent fades within an │ │ ← C[].snippet  (PII-REDACTED as returned)
│   │  hour, not as described"│ │   null snippet → "snippet unavailable" note,
│   └─────────────────────────┘ │   never fabricated (brief §5)
└───────────────────────────────┘
```

### D-replace — click a DIFFERENT [n] (even in another turn) → it REPLACES
```
Now user clicks [1] on turn t (a different turn):

turn t-2:  …[1]·[2]…      ← [2] DE-highlights (no longer active)
turn t  :  …[1*]·[2]·[3]… ← [1] becomes ACTIVE/highlighted

┌ EVIDENCE ─────────────────────┐
│ ● [1]  Returns Policy / §3    │ ← panel now shows ONLY this one citation;
│   source_id: returns#3        │   the previous [2] card is GONE, not stacked
│   type: policy                │   (criterion 5: one at a time, replace)
│   ┌─────────────────────────┐ │
│   │ "30-day return if …"    │ │ ← C[].snippet
│   └─────────────────────────┘ │
└───────────────────────────────┘
```

Notes:
- **Exactly one** citation renders at any time (criterion 5). Clicking any
  `[n]`/chip in *any* turn replaces the panel's content; there is never a second
  card, never a per-turn evidence dump, never auto-expansion.
- **Active-citation highlight:** the clicked `[n]` is marked active (lo-fi: `*`
  / filled) in its turn; clicking another de-highlights the previous and
  highlights the new one. At most one `[n]` across the whole thread is active.
- Snippet is the already-redacted `C[].snippet` shown verbatim; `null` → an
  honest "snippet unavailable" line (⚑ the null case is a copy item for handoff).

---

## 6. Responsive — rail (identity + history) + Evidence across breakpoints

Reuses the inherited breakpoints (236 | 1fr | 300 → 2col `<1080` → 1col `<760`;
Evidence → bottom sheet) from iteration-2 §9 / handoff. Only the *new* rail
contents (identity + history) need a placement rule:

### `<1080px` (2 columns)
```
┌──────────────────┬───────────────────────────────┐
│ LEFT RAIL (236)  │ CONVERSATION (1fr)            │
│ identity ▾       │ stacked turns …               │
│ + new chat       │ [composer pinned]             │
│ history (yours)  │                               │
│ scope · session  │                               │
└──────────────────┴───────────────────────────────┘
   Evidence dock HIDDEN → opens as a BOTTOM SHEET on [n] click
   (same single-citation content as §D; Esc closes — inherited a11y)
```

### `<760px` (1 column — phone)
```
┌───────────────────────────────┐
│ ☰ marketing · mktg_1 ▾   ⚙   │ ← rail COLLAPSES to a top control:
├───────────────────────────────┤   identity + a ☰ opens history as a
│ conversation (full width)     │   left DRAWER (new chat + owner rows).
│  user: "…"                    │   Scope lock + session move into the
│  assistant: …[1][2]  ▾        │   drawer / top control (iteration-2 §9).
├───────────────────────────────┤
│ [ ask…               ](send) │ ← composer pinned (16px gutter, no h-scroll)
└───────────────────────────────┘
   tap [n] → Evidence rises as BOTTOM SHEET (ONE citation, §D-one)
```

- **Identity on phone:** lives in the always-visible top control (role + user +
  `▾`) so owner is never hidden — switching it is a first-class phone action.
- **History on phone:** behind the `☰` drawer (it is navigation, not the primary
  surface); "+ new chat" sits at the drawer's top. Selecting a row closes the
  drawer and loads the thread.
- **Evidence on phone/tablet:** bottom sheet, still **one citation**, replace
  semantics identical to §D. 16px gutter, no horizontal scroll throughout.

---

## 7. Governance callouts (⚑) — where a field drives governance

| ⚑ | Where | Rule | Source |
|---|---|---|---|
| ⚑ HANDOFF | `GET /threads` | list **owner-filtered by `ID.user_id`** AND M6-scope-aware; never returns another owner's or another role's threads/turns/snippets. The one backend edge (brief §6). | `threads.user_id` / `MemoryStore` owner guard |
| ⚑ | History rows (§B) | owner-scoped — `support_1` ≠ `support_2` ≠ `marketing_1`; the observable proof of criterion 1. | `threads.user_id` |
| ⚑ | Switch flow (§3d) | center resets so no prior owner's conversation remains visible under a new identity (criterion 7). | — (UI rule) |
| ⚑ | Scope chips (restored & live) | enumerated **only** from `A.scope.categories` (+ `restricted`); never hard-coded, never widened — including on resumed/older turns (criterion 6). | `audit.scope` |
| ⚑ | Evidence snippet (§D) | the **redacted** `C[].snippet` shown as-returned; UI never un-redacts or fabricates; `null` → honest unavailable note. | `citations[].snippet` |
| ⚑ HANDOFF | Resume payload (§4) | restored turns' `A.*` + `C[]` shown as available; **mechanism undecided** (thread-detail read vs. per-turn re-fetch) — a `03_handoff.md` decision, not invented here. | — |

Non-goals carried unchanged (brief §5): no streaming (D-12), no thread
rename/search/delete, no auth (the identity switcher is demo-only).

---

*Next (after D2 review): `mockups/<surface>.html` (hi-fi, theme-aware,
single-citation Evidence, stacked turns, owner-scoped rail). The ⚑ HANDOFF items
above — `GET /threads` owner+scope filter, the resume-payload mechanism, the
row-label derivation, and the null-snippet copy — carry forward to
`03_handoff.md`.*
