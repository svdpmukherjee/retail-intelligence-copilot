# 02 · Design Decision Log — M8 Chat / Serving UI · **iteration 3**

**Design Track · iteration 3 · Stage 4 (decision log).** Written after the hi-fi
mockup (`i3/mockups/m8-chat-v3.html`) was approved at CHECKPOINT D2 (with the two
fixes applied: rail-overflow and history-timestamp-on-its-own-line). This is a
**delta** on the iteration-2 log (`design/iteration-2/02_decisions.md`): iteration-2
decisions **D-01 … D-15 carry forward unchanged by reference** — the trust strip
(D-02), the strip/evidence split (D-03), the three role shapes (D-04/D-05), scope
as a read-only fact (D-07), the state machine (D-09…D-13), theme tokens (D-14).
Iteration 3 continues the series at **D-16** and records **only** what it adds or
changes, plus where it **resolves** an iteration-2 "Pending" item.

> **Honest framing — a conversation-layer delta.** v1 (M1–M8) was an engineering
> spike. Iteration 2 made a *single* answer trustworthy. Iteration 3 makes the
> copilot feel like an owned, multi-turn conversation — on the **same** governed
> pipeline and the **same** trust/governance surface. Memory already round-trips
> server-side; these decisions are about *showing* it, not changing it.

---

## 1. Decision log (iteration-3 additions)

### 1.1 Identity & ownership

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-16** | **Identity = role + a specific user-within-role, selected by a labelled *demo* switcher — explicitly NOT a login.** The dropdown lists `support_1`, `support_2`, `marketing_1`, `executive_1`; the picked `user_id` is the owner key carried on `POST /query` and `GET /threads`. | A real login / server-asserted identity, or keeping iteration-2's anonymous `localStorage` `user_id`. | Revisits iteration-2 **D-15 §2 "Authentication/identity"**. A switchable, *visible* owner makes owner-scoping observable to a reviewer (watch `support_1` ≠ `support_2`) without pretending to be auth. Real auth (password, session trust boundary, scope derived from an authenticated principal) is a separate, larger feature and stays deferred (BACKLOG); simulating it would be theatre. The switcher is a reviewer affordance, nothing more — the label says so. |

### 1.2 The conversation shell

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-17** | **Owner-scoped left-rail history: list + resume + "+ new chat", and nothing else** — no rename, search, or delete. Rows show a derived label + relative timestamp; clicking resumes; "+ new chat" clears to the empty state. | Full thread management (rename/search/delete/pin/archive). | Revisits **D-15** and iteration-2 §2 "Deferred: conversation list / thread switcher / new chat". This is the *minimum* that makes a conversation feel real and owned. Management verbs are polish, each with its own edge cases (confirm-delete, search index, collision on rename) — pure UI surface area that proves nothing new about the governed system. Deferred to BACKLOG ("History search / rename / delete"). |
| **D-18** | **The center stacks ALL turns of the active thread** (user bubble → assistant turn), oldest→newest, scrollable, composer pinned; a follow-up **appends** below and never replaces a prior turn. | Keep iteration-2's single Q→A render (replace-on-send). | Revisits **D-15**. Memory already round-trips server-side (`audit.memory.history_turns_used`); iteration 2 only *reported* it as an audit line. Stacking turns *shows* the reasoning build up — the executive's "…and why for Beauty specifically?" follow-up stays on screen above its answer. All trust strips stay **collapsed by default** (inherited D-02) so a long thread stays scannable. |
| **D-19** | **Evidence panel = exactly ONE citation at a time.** Default is an empty prompt; clicking any `[n]`/chip in *any* turn shows one citation in full; clicking a different `[n]` **replaces** it (never stacks a second). The active `[n]` is highlighted and the highlight is **synced across the whole thread** (at most one active marker anywhere). | A per-turn evidence dump, or auto-expanding every citation of every turn. | **Refines iteration-2 D-01** for a now multi-turn thread. In a long conversation, dumping every turn's evidence buries the one source actually in question. One-at-a-time keeps the dock answering a single, precise "what is *this* claim resting on?" — the strip still answers "how" per turn (inherited D-03). Replace-not-stack keeps the dock bounded regardless of thread length. |

### 1.3 Governance now binds to real fields

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| **D-20** | **Scope chips and evidence snippets now bind to REAL response fields — resolving iteration-2 Pending #1 and #2.** `audit.scope = { restricted: bool, categories: string[] }` and the redacted `citations[].snippet: string \| null` both **shipped in M8 v2**. Scope chips are now *rendered from* `audit.scope.categories` (never hard-coded); the snippet is shown as returned. | Continuing to show illustrative/flagged mock chips and withholding snippet text (iteration-2 D-08 / Pending #1–#2). | The two iteration-2 blockers are gone: `pipeline.py` sets `audit.scope` (`result.audit["scope"] = {"restricted": bool(categories), "categories": categories}`), and `composer.py` sets `Citation.snippet` via `_snippet()` → `governance.pii.redact`, trimmed to `MAX_QUOTE_CHARS` (240). So the mockup renders chips by **reading the object** and shows a visibly-redacted snippet (e.g. a `[EMAIL]`/`[PHONE]` token). **The snippet is PII-redacted at source; the UI shows it verbatim and never un-redacts, re-derives, or fabricates it.** A `null` snippet → an honest "snippet unavailable" note, never invented text. (Iteration-2 Pending #3, `source_type`, stays frontend-derived — unchanged.) |
| **D-21** | **Resume shows what was actually stored; it does not re-run the pipeline, and it does not pretend audit/citations are available when they are not persisted.** The honest minimum for the reference build: a thread-detail read returns the stored Q/A **text**; restored assistant turns carry a muted "historical turn" note rather than a fabricated live trust strip/evidence. Full-fidelity resume (per-turn audit + citations) is flagged as a **pending backend change** (persist them at answer time). | (b) re-running `POST /query` per restored turn to rebuild audit/citations. | Re-running recomputes, costs tokens/latency, and can produce a *different* answer — it would misrepresent "what actually happened," the opposite of this system's point. And the M5 `messages` table stores only redacted `content` (role_kind/content/turn) — **audit and citations are not persisted today**. So the honest path is: read back the stored text, and be explicit that reasoning/evidence for old turns is not replayable until the backend persists it. The mockup renders full strips on restored turns as a *canned convenience* (flagged), exactly as iteration-2 flagged reused session figures. See `03_handoff.md` §2 for the specced mechanism. |

---

## 2. Deferred / where we stopped and why

Conscious stops for a reference build. **Iteration-2 §2 deferred items still hold
by reference** — streaming (still a PRD §5 non-goal, D-12), admin/analyst bespoke
shapes, and evidence-span highlighting. Iteration 3 *resolves* iteration-2's "3
pending backend fields" item for scope + snippet (D-20); `source_type` remains
frontend-derived. New/updated stops:

| Deferred item | Why stopped here | What a later pass would add |
|---|---|---|
| **Thread rename / search / delete.** | The rail is list + resume + new only (D-17). Management verbs are UI polish with their own edge cases and prove nothing about the governed pipeline. | Rename, a search/filter box over labels, delete-with-confirm, pin/archive. BACKLOG "History search / rename / delete". |
| **Real authentication / server-asserted identity.** | The switcher is a *demo* owner selector (D-16), not a login. No password, no session trust boundary, scope still keyed off a self-selected role. | Real auth, role asserted by the identity provider (not client-chosen), `user_id` as an authenticated principal, and `GET /threads` authorising the caller instead of trusting a round-tripped id. BACKLOG "Real auth". |
| **Full-fidelity resume of audit + citations on old turns.** | `messages` persists redacted text only; audit/citations are not stored (D-21). Replaying them would require either a schema add or a costly re-run. | Persist each assistant turn's `audit` + `citations` (JSON) at answer time, then a thread-detail read returns them so restored turns are fully inspectable (trust strip + evidence) like live ones. Specced as a pending backend change in `03_handoff.md` §2. |
| **Pagination / search of long histories.** | Canned lists are short; the rail renders all of a (small) owner's threads. At real scale an unbounded list is a performance and findability problem. | Server-side pagination / lazy-load on the `GET /threads` list and a search affordance (ties to the rename/search defer above). |
| **Cross-device / shared identity continuity.** | A demo identity is a local selection; there is no notion of the *same* user across devices or sessions beyond the round-tripped `user_id`. | Identity tied to an authenticated account so history follows the user across devices (depends on the auth defer). |
| **Restored-turn trust/evidence shown as live in the mockup.** | A *mockup* convenience (canned): restored turns show full strips/evidence so the flow is clickable at D2. Not a design claim about the build. | In the build, restored-turn inspectability depends on the D-21 persist-and-read-back change; until then restored turns carry the muted "historical turn" note. |

---

*Paired with: `03_handoff.md` (the build spec for the M8 v3 rebuild). Sources:
`i3/00_brief.md`, `i3/01_wireframes.md`, `i3/mockups/m8-chat-v3.html` (approved
D2); the iteration-2 log `design/iteration-2/02_decisions.md` (D-01…D-15, inherited);
and the real contract in `backend/app/main.py`, `agents/pipeline.py`,
`agents/composer.py`, `memory/store.py`, `memory/schema.py`, `memory/manager.py`.*
