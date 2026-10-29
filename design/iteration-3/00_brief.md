# 00 · Design Brief — M8 Chat / Serving UI · **iteration 3**

**Design Track · iteration 3 · Stage D1 (brief).** Stops at CHECKPOINT D1 for
human approval. No wireframes, mockups, decisions, handoff, or application code
yet — this document fixes the *problem framing* for iteration 3 only.

> **Honest framing — this is a delta, not a rewrite.** v1 (M1–M8) was an
> **engineering spike**, built first and dated in `context/WORKLOG.md` + git.
> **Iteration 2** was a design-driven redo of the M8 chat *surface* on the
> unchanged backend; it shipped as M8 v2 (closed 2026-10-28, visual-fidelity
> `/change` closed 2026-10-29). Design did **not** come first. **Iteration 3**
> layers on that working, approved surface. It deliberately picks up the one
> thing iteration 2 **consciously deferred**: the multi-turn conversation /
> memory layer (iteration-2 `02_decisions.md` **D-15** and its §2 "Deferred:
> multi-turn thread history, conversation list, new chat, thread switcher").
> This brief says plainly what iteration 2 already decided and only what
> iteration 3 *adds or changes*; it references decision IDs (D-xx) rather than
> restating them. BACKLOG already names this work **M8 v3**.

---

## 1. Objective

Iteration 2 made a *single* answer trustworthy: one Q→A turn, its reasoning
glanceable (D-02), its evidence inspectable (D-01), its scope legible (D-07).
What it is **not** yet is a *conversation* — the center renders one turn, memory
is only *reported* as an audit line (D-15), and "whose session is this" is an
anonymous `localStorage` id.

**Iteration 3 makes the copilot feel like a real, owned, multi-turn
conversation — while keeping every iteration-2 trust and governance property
exactly in force.** Memory already works server-side (threads/messages persist
and round-trip); iteration 3 *shows* it: a switchable identity, a left-rail list
of that identity's past threads, a resumable center panel that stacks all turns
of the active thread, and an evidence panel refined for many turns. Nothing about
the governed pipeline or the audit/trust surface changes — this is a
conversation-layer delta on top of a surface the human already approved.

---

## 2. Personas & identity

The three PRD §2 personas are **unchanged** from iteration-2 §2 (support agent,
marketing/product, executive) with the same jobs-to-be-done, backend routes, and
M6 scopes. What iteration 3 adds is a **user-within-role**: the same role can now
be held by a *specific* demo identity, so "whose conversations am I seeing"
becomes concrete and owner-scoping is visible to a reviewer.

| Demo identity | Role (persona) | M6 scope (unchanged) | Why it exists in the demo |
|---|---|---|---|
| `support_1` | support | **Scoped** (Electronics, Home_and_Kitchen, Automotive, Pet_Supplies) | Two support users prove threads are **owner-scoped**: `support_1` sees only `support_1`'s threads, never `support_2`'s. |
| `support_2` | support | same as `support_1` | The second owner that makes owner-scoping observable (same role, different threads). |
| `marketing_1` | marketing | **Scoped** (Beauty_and_Personal_Care, Toys_and_Games, Books) | One marketing owner; its history never shows support's or executive's threads. |
| `executive_1` | executive | **Unrestricted** (`{}`) | One unrestricted owner; proves the rail stays owner-scoped even when the role is unrestricted. |

**The identity switcher is a demo convenience, not auth.** It is explicitly
labelled as such. Iteration 2's picker was role-only with an anonymous
`localStorage` `user_id` (D-15 §2 "Authentication/identity" deferred, and
BACKLOG "Real auth"). Iteration 3 makes the **user-within-role** selectable so a
thread has a real, switchable **owner** — but there is still no login, no
password, no server-asserted identity, no session trust boundary. Real auth
remains deferred (BACKLOG). Switching identity is a reviewer affordance to *see*
owner-scoping, nothing more.

---

## 3. What iteration 2 deferred that iteration 3 adds

Four concrete additions. Each revisits a specific iteration-2 decision and serves
a named persona job. Everything else in the iteration-2 handoff stays as-is.

| # | Addition | Revisits | Persona job it serves |
|---|---|---|---|
| **A** | **Identity = role + a specific user-within-role**, selectable (a labelled *demo* switcher, not login). Threads get a real, switchable owner. | D-15 §2 (anonymous `user_id`); BACKLOG "Real auth" (stays deferred — this is not auth) | Any persona: "this is *my* workspace." A reviewer can watch `support_1` vs `support_2` to confirm owner-scoping is real, not asserted. |
| **B** | **Left-rail history list** of the current identity's past threads → click a thread to **resume** it (loads its turns); a **"+ new chat"** control starts a fresh thread. | D-15 + §2 "Deferred: conversation list / thread switcher / new chat" | Support agent working several cases across a shift; marketing revisiting last quarter's theme question — return to a prior line of inquiry instead of re-asking. |
| **C** | **Center panel stacks ALL turns of the active thread** and keeps them visible, so a follow-up and its answer stay on screen. | D-15 / iteration-2 §2 ("renders a single Q→A turn") | Executive asking a follow-up ("…and why for Beauty specifically?") and seeing the thread of reasoning build — the same memory the backend already round-trips, now actually *shown*. |
| **D** | **Evidence panel becomes click-to-inspect: exactly ONE citation in full, only on `[n]`/chip click** — no per-turn evidence dump, no auto-expansion of every citation across the thread. | D-01 (docked Evidence panel), refined for a now multi-turn thread | All personas: in a long thread, inspect the *one* source behind the *one* claim in question without a wall of evidence from every prior turn drowning it. |

Note the division of labour is unchanged from D-03: the **trust strip** still
answers "how" (per-turn, from `audit`), the **Evidence panel** still answers
"what" (evidence bodies). Iteration 3 only changes the Evidence panel's *scoping*
to one-at-a-time across a multi-turn thread (D) and adds the conversation shell
around both (A–C).

---

## 4. UX success criteria (checkable)

New, verifiable criteria for the four additions. **Iteration 2's trust/
governance criteria (its §4 criteria 1–6: why-in-one-action, visible trust,
legible scope, role→render, every-state, cost/latency honesty) remain in force
by reference** and must not regress — they are not re-listed here.

1. **Owner-scoped rail.** Switching identity reloads the left rail to show **only
   that identity's** threads; `support_1`'s list never shows `support_2`'s
   threads, and no identity's rail shows another role's threads. (Verifiable by
   switching `support_1` ↔ `support_2` ↔ `marketing_1`.)
2. **Resume restores the whole thread.** Clicking a thread in the rail loads
   **all** its prior turns (every Q and A, oldest→newest) into the center panel,
   not just the latest; the trust strip / evidence affordances work on each
   restored turn exactly as on a live one.
3. **New chat starts clean.** "+ new chat" opens an empty thread (iteration-2
   empty state) owned by the active identity; the first answer creates a thread
   that then appears in the rail.
4. **Turns stack and stay.** Asking a follow-up keeps the previous turn(s)
   visible above it; the thread is scrollable and ordered; no prior turn is
   replaced or discarded.
5. **One citation at a time.** Clicking an `[n]` (or chip) shows **exactly one**
   citation in full in the Evidence panel; clicking a different `[n]` — in the
   same or a different turn — **replaces** it (never stacks a second). No turn
   auto-dumps its evidence.
6. **Scope stays derived, across turns.** Every scope statement/chip comes only
   from `audit.scope` (`{ restricted, categories }`) — never hard-coded in the
   UI, and never widened — including on resumed/older turns.
7. **Governance holds across the conversation layer.** No path in the rail,
   resume, or evidence inspection surfaces a thread, turn, or snippet outside the
   active role's M6 scope or outside the active identity's ownership.

(1–4 are the primary bar for iteration-3 D1; 5–7 preserve the iteration-2
guarantees under the new multi-turn surface.)

---

## 5. Constraints

- **Governance intact (same spirit as iteration-2 brief §5, D-05/D-07/D-08).**
  - **Scope comes from `audit.scope`** — a now-real response field
    (`{ restricted: bool, categories: string[] }`, set in `pipeline.py` ~line
    104). The UI enumerates chips from it and **never hard-codes category names**.
  - **Snippets are the already-redacted `citations[].snippet`** — a PII-redacted
    excerpt set in `composer.py` (`_snippet` via `governance.pii.redact`, trimmed
    to `MAX_QUOTE_CHARS`). The UI shows the redacted text as returned; it **never
    un-redacts, re-derives, or fabricates** evidence text.
  - **No path to out-of-scope data.** The thread-history list is **owner-scoped**
    (filter by `user_id`, the exact owner guard `MemoryStore.append_message` /
    `recent_messages` already enforce) **and M6-scope-aware** — it must not
    surface threads, turns, or evidence the active role may not see. Design must
    not outrun governance.
- **No auth.** The identity switcher is a demo convenience, not a login (§2).
  Real auth stays deferred (BACKLOG).
- **No thread management beyond list + resume + new.** No rename, search, or
  delete of threads — explicitly deferred per BACKLOG ("History search / rename /
  delete"). Iteration 3 ships the minimum that makes conversation feel real.
- **Delta, not rewrite.** Iteration 3 adds the conversation shell and the
  evidence refinement; it does **not** re-open the iteration-2 trust strip, role
  shapes, state machine, cost/latency surface, theme tokens, or a11y contract —
  those are inherited. Carried non-goals still hold: no streaming (D-12), no
  backend pipeline changes beyond the single read-only edge in §6.
- **Reference-grade, not production.** Portfolio clarity over breadth. The
  artifact page contract is inherited (D-14): light+dark tokens, 16px gutter,
  works at phone width.

---

## 6. Backend note (flag for handoff, not designed here)

Iteration 3 binds almost entirely to the **existing** `POST /query` plus the two
fields that **shipped in M8 v2** and are now real contract (resolving two of
iteration-2 handoff's three "Pending" items):

- `audit.scope = { restricted: bool, categories: string[] }` (resolves Pending #2)
- `citations[].snippet: string | null`, PII-redacted at source (resolves Pending #1)

The **one** backend edge iteration 3 needs is a single **read-only** endpoint:

> **`GET /threads`** — lists the calling identity's past threads (to populate the
> left-rail history list). It must be **owner-checked** (filter by `user_id`,
> exactly like the owner guard in `MemoryStore.append_message` /
> `recent_messages`) and **M6-scope-aware** (never return threads or content the
> active role may not see). The M5 tables already exist (`MemoryStore`:
> `threads(id, user_id, role, created_at…)`, `messages(thread_id, turn,
> role_kind, content)` in `backend/memory/`).

This is **noted, not specced** — the endpoint's request/response shape, resume
payload, and bindings are for `03_handoff.md` later. Everything else binds to the
already-shipped contract; this is the sole backend edge iteration 3 introduces.

---

*Next (gated on D1 approval): `design/iteration-3/01_wireframes.md` — lo-fi annotated
layouts for the conversation shell and every state of the four additions
(owner-scoped rail, resume, stacked turns, one-at-a-time evidence). This is a
brief only — no pixels.*
