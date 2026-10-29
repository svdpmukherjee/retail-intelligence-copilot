# Spec M8 v3: Serving & UI — conversation / memory layer (design-driven rebuild)

> **Iteration 3, a delta on v2 — not a fresh build.** M8 is DONE as v1 (spike)
> and v2 (`.claude/specs/M8v2_serving_ui.md`, the shipped role-adaptive chat with
> the ported mockup stylesheet). This spec wraps a **conversation shell**
> (identity switcher, owner-scoped history rail, stacked multi-turn center,
> one-at-a-time Evidence, phone history drawer) around that working v2 surface,
> driven by `design/iteration-3/03_handoff.md` (authoritative; a delta on
> `design/iteration-2/03_handoff.md`, which stays in force for everything not
> named in iteration 3). The visual target is
> `design/iteration-3/mockups/m8-chat-v3.html`, but the build honors §2's
> **honest degrade**, NOT the mockup's canned full strips on restored turns.
> **The backend pipeline does not change.** The only backend work is two
> read-only routes + one new `MemoryStore.list_threads`. The v2 spec and note
> are left intact.

## User story
As a returning retail business user (support / marketing / executive) switching
between demo identities, I want my past conversations listed and resumable, and I
want follow-up questions to stack in one continuous thread, so that the copilot
feels like an ongoing, owner-scoped conversation — while scope stays enforced
server-side and restored turns never fabricate trust or evidence they can't prove.

## Module acceptance criteria
- [ ] **One backend edge, read-only, owner- AND role-scoped.** `GET /threads?user_id=&role=`
      lists only the active identity's threads for the active role
      (`WHERE t.user_id=%s AND t.role=%s`), and `GET /threads/{id}?user_id=`
      returns a thread's stored turns only to its owner (same guard shape as
      `recent_messages`; non-owner/unknown → never another owner's data). The
      pipeline, `POST /query`, and `schema.py` are unchanged; `label` is **derived
      in the query** from the first (redacted) user message, NOT a new column.
- [ ] **Governance invariant (M6) holds.** The list endpoint returns no turn
      content and no snippets. Scope chips still come only from
      `audit.scope.{restricted,categories}`; snippets still come from redacted
      `citations[].snippet` shown verbatim (`null` → "snippet unavailable",
      never fabricated); a grep for category names across `frontend/src` stays
      empty. The identity switcher only *selects* a role/user — scope is enforced
      at retrieval, server-side, never widened client-side.
- [ ] **Honest resume degrade (D-21).** Restored turns render the stored redacted
      text + a muted "historical turn — reasoning & evidence not stored for
      replay" note; they do NOT fabricate a trust strip or clickable evidence.
      Live turns asked this session keep their full trust strip + one-at-a-time
      evidence from the in-memory `QueryResponse`.
- [ ] **Conversation shell.** Identity switcher (demo, not a login) + owner-scoped
      history rail with "+ new chat"; a stacked multi-turn center where follow-ups
      append and post the active `thread_id`; a one-at-a-time Evidence panel
      (dock / phone bottom sheet) showing exactly one citation; a phone history
      drawer. Switching identity resets the center and reloads the rail to the
      new owner.
- [ ] **Non-goals honored:** no streaming, no auth, no thread rename / search /
      delete; §2 option (c) (persisting per-turn audit/citations) is NOT built,
      only named as a future schema change.
- [ ] **Accessibility deltas (handoff §5)** met on top of the inherited v2 a11y:
      labelled identity `<select>`, history rows as real `<button>`s with
      `aria-current` on the active one, labelled "+ new chat", phone-drawer focus
      management (focus-in, Escape closes + returns focus, backdrop close,
      `aria-expanded`), one-citation replace that keeps focus sane, `aria-live`
      across appended turns.
- [ ] `npm run build` (typecheck + vite) passes; the scoped backend test file
      passes; one real end-to-end smoke exercises list → resume → follow-up on a
      live thread. **Cost $0** (free provider mode; nothing provisions).
- [ ] **Browser visual-QA gate (required, module-level):** desktop + phone, light
      + dark; every structurally distinct new surface (history rail populated /
      empty / active-row, stacked multi-turn with a live turn + a restored turn
      carrying the muted note, one-at-a-time Evidence dock + phone bottom sheet,
      phone history drawer) matches the v3 mockup; governance (owner-scoped list,
      scope chips from `audit.scope`, no fabricated restored-turn strip) verified
      live in the browser. If the browser can't be driven, the tester reports it
      plainly — never a silent PASS.

## Sub-modules (ordered, each build → verify → integrate)

### M8v3.1 Backend edge — `MemoryStore.list_threads` + `GET /threads` + `GET /threads/{id}`
- Goal: give the frontend two real, read-only, owner-scoped endpoints to bind to;
  no pipeline change, no schema change.
- Acceptance criteria (trace: handoff §1, §2 option a):
  - [ ] New `MemoryStore.list_threads(user_id, role) -> list[...]`, parameterised,
        `WHERE t.user_id=%s AND t.role=%s`, `LEFT JOIN messages`, `GROUP BY t.id`,
        `ORDER BY t.created_at DESC`; `label` derived in the query from the first
        user message (`role_kind='user'` at `min(turn)`, already redacted,
        truncated ~48 chars); `turn_count` a simple `COUNT` aggregate. No `label`
        column is added to `schema.py`.
  - [ ] `GET /threads?user_id=&role=` → `{ "threads": [ { id, label, created_at,
        turn_count } ] }`; returns no turn content and no snippets.
  - [ ] `GET /threads/{id}?user_id=` → `{ thread_id, role, turns: [ { turn,
        role_kind, content } ] }` ordered oldest→newest, reusing the
        `recent_messages(..., user_id=…)` owner guard; a non-owner or unknown
        thread gets empty/`404`, never another owner's rows.
  - [ ] A scoped test proves: `support_1` never receives `support_2`'s threads;
        a thread created under one role is not listed under another role; a
        non-owner `GET /threads/{id}` yields no content.
- Build steps:
  1. `memory/store.py`: add `list_threads`; if a typed row is wanted, add a small
     `ThreadListRow` BaseModel in `memory/schema.py` (model only — **no new table
     column**). Keep the per-call-connect, fully-parameterised style of the file.
  2. `app/main.py`: add two `async` routes using `asyncio.to_thread` for the
     blocking store calls (mirror the `new_thread` pattern); return typed
     Pydantic response models; fail loud-but-clean with `HTTPException` + JSON
     `detail` on bad input, never an unhandled 500.
  3. Do not touch `agents/pipeline.py`, `agents/composer.py`, `memory/manager.py`,
     `POST /query`, or `schema.py`'s DDL/columns.
- Files to touch: `backend/memory/store.py`, `backend/app/main.py` (routes +
  response models), optionally `backend/memory/schema.py` (row model only), new
  `backend/tests/test_threads_endpoint_m8v3.py`.
- Integration point: additive routes beside the unchanged `POST /query` / `GET
  /roles`; the owner key is the same `user_id` the client already round-trips.

### M8v3.2 Frontend contract + API client additions
- Goal: mirror the two new endpoints in TypeScript so the UI binds to reality.
- Acceptance criteria (trace: handoff §0, §3 new bindings):
  - [ ] `types.ts` adds `ThreadListItem { id: string; label: string; created_at:
        string; turn_count: number }` and `ThreadDetail { thread_id: string;
        role: string; turns: { turn: number; role_kind: "user" | "assistant";
        content: string }[] }`. No change to `Citation`/`Audit`/`QueryResponse`
        (already carry `snippet` + `scope` from v2).
  - [ ] `client.ts` adds `getThreads(userId, role)` and `getThread(id, userId)`
        using the existing `request<T>`/`ApiError`/`BASE_URL`; query params are
        URL-encoded; existing `getRoles`/`postQuery` unchanged.
  - [ ] `npm run typecheck` passes.
- Build steps: extend `types.ts`; add the two client methods; keep `ApiError`
  and `request` as-is.
- Files to touch: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`.
- Integration point: consumed by M8v3.3 (rail) and M8v3.4 (resume); calls the
  live M8v3.1 backend.

### M8v3.3 Identity switcher + owner-scoped history rail (list + "+ new chat")
- Goal: the rail gains a demo identity selector and a real history list owned by
  the active identity, plus "+ new chat".
- Acceptance criteria (trace: handoff §3 identity switcher / history list / row,
  switch + new-chat flows, D-16/D-17):
  - [ ] Identity switcher: a labelled `<select>` ("Demo identity") of demo
        identities (`support_1/2`, `marketing_1`, `executive_1`); its demo-not-a-
        login status is textually present (not colour-only). Selecting an identity
        sets `user_id` (owner key, sent on `POST /query` + `GET /threads`) and its
        `role` (→ `req.role` and the answer shape).
  - [ ] History list binds `GET /threads` rows; states: **populated** (rows with
        `label` + relative `created_at`), **empty** ("No conversations yet…"),
        **row active** (exactly one, `aria-current="true"`). Rows are real
        `<button>`s. "+ new chat" is a labelled `<button>` at the top of the list.
  - [ ] **Switch identity** reloads the rail to the new owner's `GET /threads`
        AND resets the center to the new-chat empty state (nothing from the prior
        owner lingers). **"+ new chat"** clears the center to empty with no row
        active; the new thread does not appear in the rail until its first answer
        persists — on the `QueryResponse` landing (`thread_id` now set), re-fetch
        `GET /threads` so the new row appears and becomes active.
- Build steps: replace the v2 anonymous `localStorage` user-id with the identity
  switcher as the owner source; add `components/IdentitySwitcher.tsx` and
  `components/HistoryRail.tsx` (+ `HistoryRow`); wire fetch/active-row/new-chat
  state in `App.tsx`; style to the v3 mockup's rail DOM. Scope card re-derives
  from the new role meanwhile (reuse v2 `scope_for_role`/`audit.scope`).
- Files to touch: `frontend/src/App.tsx`, `frontend/src/components/RoleRail.tsx`
  (host the switcher + history list), new `IdentitySwitcher.tsx` /
  `HistoryRail.tsx`, `frontend/src/App.css` (rail history styling from the v3
  mockup).
- Integration point: imports M8v3.2 `getThreads`; the active identity feeds the
  `POST /query` round-trip and the stacked center built next.

### M8v3.4 Stacked multi-turn container + resume wiring (honest degrade)
- Goal: turn the v2 single-Q→A center into a scrollable vertical stack of all
  active-thread turns, with resume restoring prior turns honestly.
- Acceptance criteria (trace: handoff §2 option a, §3 stacked-turn container +
  resume flow, §4, D-18/D-21):
  - [ ] Center renders a stack of turns (oldest→newest), composer pinned; a
        follow-up appends a new user turn + assistant turn and posts the active
        `thread_id`; earlier turns remain while the newest is in-flight (skeleton
        as the newest turn only).
  - [ ] **Live turns** (asked this session) keep the full v2 trust strip + one-at-
        a-time evidence from their in-memory `QueryResponse`; each assistant turn
        still selects its v2 role shape (support/marketing/executive/default),
        charts still gated on `"sql" ∈ audit.sources`.
  - [ ] **Resume** (row click) calls `GET /threads/{id}`, stacks restored turns;
        restored assistant turns render stored redacted `content` in the role
        shape but carry a muted "historical turn — reasoning & evidence not stored
        for replay" note and **no** trust strip / clickable evidence (no `audit`
        or `citations` fabricated). The row goes active (`aria-current`); a
        follow-up posts with the resumed `thread_id`.
- Build steps: lift center state from a single response to a `turns[]` list in
  `App.tsx`, each item tagged `live` (holds its `QueryResponse`) or `restored`
  (holds stored text only); add `components/StackedTurns.tsx` and a
  `RestoredTurn` rendering (reuse `UserTurn`/`AssistantTurn`; gate strip/evidence
  on `live`); the per-response `derivePanelState` stays per-live-turn. The muted
  note is authored copy in `copy.ts`.
- Files to touch: `frontend/src/App.tsx`, `frontend/src/components/ConversationPanel.tsx`,
  new `StackedTurns.tsx` (+ restored-turn markup), `frontend/src/components/AssistantTurn.tsx`
  (accept a `historical` prop that suppresses strip/evidence and shows the note),
  `frontend/src/copy.ts`, `frontend/src/App.css`.
- Integration point: consumes M8v3.2 `getThread` and the M8v3.3 active-row click;
  reuses every v2 shape/strip/chip component for live turns.

### M8v3.5 One-at-a-time Evidence panel + phone history drawer + a11y deltas
- Goal: constrain Evidence to exactly one citation, add the phone history drawer,
  and land the handoff §5 a11y deltas.
- Acceptance criteria (trace: handoff §3 one-at-a-time Evidence / phone drawer,
  §5, D-19):
  - [ ] Evidence panel shows **exactly one** citation at a time (default empty
        prompt; one shown; replaced in place on a different `[n]`); binds
        `citations[].n/.label/.source_id/.snippet` (`null` → "snippet unavailable",
        never fabricated); type tag UI-derived as in v2. On phone: closed ↔ bottom
        sheet. Clicking a new `[n]` updates the single item in place, focus stays
        on the clicked marker, the previously-active marker de-highlights (no focus
        trap, no scroll jump).
  - [ ] Phone history drawer: `☰` opens history off-canvas (identity stays in the
        top control); opening moves focus into the drawer; Escape closes and
        returns focus to `☰`; backdrop click closes; `aria-expanded` on the toggle;
        same `GET /threads` data as the desktop rail.
  - [ ] A11y deltas verified: identity `<select>` labelled; history rows real
        `<button>`s with `aria-current` on the active one; "+ new chat" labelled;
        `aria-live` announces a newly-appended turn once rendered. Inherited v2
        a11y still holds.
- Build steps: adjust `EvidencePanel.tsx` to a single-item model (current activeN
  already single — enforce "replace in place" + focus-stays-on-marker); add
  `components/HistoryDrawer.tsx` reusing `HistoryRail`'s list and the v2
  bottom-sheet focus pattern; add the `☰` toggle to the phone chrome; finalize
  focus/`aria-*` in markup + CSS.
- Files to touch: `frontend/src/components/EvidencePanel.tsx`, new `HistoryDrawer.tsx`,
  `frontend/src/App.tsx` (drawer toggle + focus plumbing), `frontend/src/App.css`.
- Integration point: completes the shell; consumes M8v3.3's list and M8v3.4's
  citation-click handler; closes the module.

## Test plan
- **M8v3.1** (tester, scoped): run `backend/tests/test_threads_endpoint_m8v3.py`
  only — **not the full suite** (it hangs on torch downloads; see tester-scope
  memory). Asserts owner isolation (`support_1` vs `support_2`), role filtering
  (same user, different role not listed), server-derived `label`/`turn_count`
  shape, and non-owner `GET /threads/{id}` returns no content.
- **M8v3.2**: `npm run typecheck` passes against the new types + client methods.
- **M8v3.3 / .4 / .5**: `npm run build` passes after each; per-sub-module
  scripted/manual check of the added surface (rail list + new-chat + identity
  switch reset; stacked turns + resume with the muted historical note on restored
  turns; one-at-a-time Evidence + phone drawer focus). Build + typecheck is the JS
  gate (v2 convention — no JS unit runner).
- **Governance greps (hold after .3–.5):** zero literal category names in
  `frontend/src`; no un-`redact`-ed snippet path introduced; the list endpoint
  returns no turn content/snippets (asserted in .1).
- **Browser visual-QA (required module gate):** backend `PROVIDER_MODE=free`
  (`uvicorn app.main:app`) + `npm run dev` at `localhost:5173`; desktop (1440px)
  and phone (500px), light **and** dark. Confirm against the v3 mockup: history
  rail populated / empty / active-row; stacked multi-turn with a live turn (full
  strip + evidence) AND a restored turn (muted historical note, no strip/
  evidence); one-at-a-time Evidence dock + phone bottom sheet; phone history
  drawer (open/Escape/backdrop). Verify live that the list is owner-scoped and
  scope chips come from `audit.scope`. If the browser can't be driven, report it
  plainly — not a silent PASS.
- **Module end-to-end smoke** (one real run, per `.claude/rules/testing.md`):
  with the live stack, as one identity ask two questions in one thread (follow-up
  posts the same `thread_id`), confirm both stack with full live strips; "+ new
  chat" then a question creates a second thread that appears in the rail on
  landing; click the first thread's row → `GET /threads/{id}` restores its turns
  with the muted historical note (no fabricated strip); switch identity → rail
  reloads to the new owner and the center resets. If the live LLM/DB path is
  unavailable, the tester reports it plainly — not a silent PASS.

## Security & cost notes
- **Cost: $0.** Free provider mode; no cloud provisioning, no embedding/cluster
  runs; deployment stays INERT as in v1/v2. No cap needed (nothing provisions).
  CHECKPOINT 1 is also the (nil) cost go-ahead.
- **Access control stays server-side.** Both new routes are read-only and
  owner-filtered (`WHERE user_id=%s`), plus `GET /threads` role-filtered
  (`AND role=%s`), using the same guard shape as `append_message` /
  `recent_messages` — a client-supplied thread list is never trusted. The
  identity switcher is a **demo owner selector (D-16), not authentication.**
- **No new PII surface.** `label` is derived from the already-`_redact`-ed first
  user message; the list returns no snippets; `GET /threads/{id}` returns stored
  (already-redacted) `content` only. Snippets on live turns stay the v2
  `redact()`-ed `citations[].snippet`. Secrets unchanged (`.env`;
  `DATABASE_URL` required for memory; `VITE_API_BASE_URL` documented).
- **M6 scope invariant:** scope chips only from `audit.scope`; no hard-coded
  category literals (grep guard); scope never widened client-side.

## Out of scope (handoff §6 / iteration-2 §6)
- **No streaming**, **no authentication** (identity switcher is a demo owner
  selector; server still owner-filters and never trusts a client list).
- **No thread rename / search / delete** — list + resume + "+ new chat" only.
- **§2 option (c): persisting per-turn `audit` + `citations`** for full-fidelity
  restored turns (e.g. an `assistant_meta` JSONB on `messages` or a sibling table,
  written in `MemoryManager.persist`, returned by `GET /threads/{id}`) is a
  **separate schema change, NOT built here** — it is named only as a future step.
  Until it lands, restored turns degrade honestly with the muted note.
- **No backend pipeline / `POST /query` / `schema.py` column change**; the only
  backend work is the two read-only routes + `MemoryStore.list_threads`.
- The v3 mockup's canned full strips on restored turns are **not** reproduced
  (D-21). Live Azure provisioning/deploy, TLS, custom domains unchanged (inert).

---
**CHECKPOINT 1 report (for the orchestrator):**
- Spec: `.claude/specs/M8v3_serving_ui.md`
- Sub-modules: M8v3.1 backend edge (`list_threads` + `GET /threads` + `GET
  /threads/{id}` + scoped tests) · M8v3.2 frontend types + client methods ·
  M8v3.3 identity switcher + owner-scoped history rail (+ "new chat") · M8v3.4
  stacked multi-turn container + resume wiring (honest degrade) · M8v3.5
  one-at-a-time Evidence + phone history drawer + a11y deltas.
- 3-line summary: Wraps a conversation/memory shell around the shipped v2 chat on
  the unchanged pipeline, adding two read-only owner- AND role-scoped endpoints
  and one `MemoryStore.list_threads` (label derived in-query, no schema change).
  Live turns keep the full trust strip + one-at-a-time evidence; restored turns
  degrade honestly with a muted "historical turn" note, never fabricating a strip
  or evidence (D-21), and governance stays server-side with scope chips only from
  `audit.scope`. A required browser visual-QA gate (desktop + phone, light + dark)
  proves the new surfaces match the v3 mockup.
- Cost: **$0**, no cap needed (free mode; nothing provisions; deployment inert).
