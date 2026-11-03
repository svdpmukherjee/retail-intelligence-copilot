# Spec M8v4: Serving UI — user-centred declutter + trust redesign (iteration 4)

## User story
As a non-technical retail user, I want the copilot to answer my question in plain
language with readable, clickable sources and nothing else on screen, so that I can
trust the answer without being shown any system internals.

## Scope framing
SDLC **iteration 4**: a frontend-and-copy redesign on the **unchanged** pipeline,
plus **exactly one** additive backend field — `citations[].display_label`. Primary
inputs: `design/iteration-4/03_handoff.md` (authoritative build spec) and
`design/iteration-4/mockups/m8-chat.html` (approved D2 visual/interaction contract).
Governing rule: `.claude/rules/ux-surface.md`. Everything not named in i4 follows the
inherited `design/iteration-2/03_handoff.md` + `iteration-3/03_handoff.md`.

**Out of scope — do NOT touch:** B-15 (vague-follow-up routing), B-16 (audit
user_id/evidence enrichment), the pipeline / retrieval / governance / memory, and the
`GET /threads` + `GET /threads/{id}` endpoints. Restored-turn persisted citations
stays an open backend change (handoff §3.1) — not built here.

**Governance invariant:** scope is still enforced server-side at retrieval; the UI
never widens scope; category names are never hard-coded (derived from `audit.scope`);
charts stay gated on `"sql" ∈ audit.sources[]`.

## Module acceptance criteria
- [ ] A live `POST /query` (free mode) returns a grounded, cited answer whose every
      `citations[].display_label` is human-readable with **no** raw id / ASIN / slug /
      filename; the existing `citations[].label` is unchanged.
- [ ] Across a clean grounded answer and a vague follow-up, the chat DOM shows **0**
      occurrences of each forbidden-surface token (handoff §5 list below).
- [ ] The rebuilt surface matches the mockup: left rail (brand + demo switcher + owner
      history), bounded scrollable transcript (newest at bottom, auto-scroll),
      one-source-at-a-time evidence dock/sheet, re-worded honest states.
- [ ] Source chips render `Source: <display_label>`, are real `<button>`s, highlight
      one-active-at-a-time across the thread, and reveal a redacted `snippet` on click.
- [ ] `SessionCard`, `TrustStrip`, and the technical `ScopeCard` presentation no longer
      appear anywhere in the chat; brand tagline is `grounded · cited` (no `$0/query`);
      header reads `answering as: <role>` (no intent).
- [ ] Carry-forward: a support user asks a question + a vague follow-up and gets cited
      answers without ever seeing a system metric or internal id.

**Forbidden-on-surface list (expected DOM count 0 each):** `thread_id`, `session_id`,
token counts, `cost_usd`, `latency_ms`, `intent`/routing labels, `tool_path`, model
slugs, provider names, raw `audit` JSON, and raw grounding tokens (`extractive`,
`llm`, `none`, `sql_rag`, `llm draft blocked`, "query failed", "not filtered",
"no session trust").

## Sub-modules (ordered, each build → verify → integrate)

### M8v4.1 Backend edge — `citations[].display_label`
- Goal: add the one new field so the chip has a human-readable binding; unblocks all chip work.
- Acceptance criteria:
  - [ ] `Citation` gains `display_label: str`; existing `label` and `snippet` unchanged.
  - [ ] Derivation by source type: **review** → product title if available, else
        `customer review · <Category>` (underscores→spaces, title-cased); **doc** →
        prettified title, optionally `<Title> · §<section>` (never the slug/filename);
        **SQL** → `Calculated from your data`. No raw ASIN / id / slug / user text in it.
  - [ ] `POST /query` response includes `display_label` on each citation (flows via
        `QueryResponse(AnswerResult)` inheritance — no main.py change needed, verify).
- Build steps:
  1. In `composer.py`, add a `_display_label(hit: SearchHit) -> str` helper (and a
     constant/branch for the SQL source) deriving from `chunk.source_type`,
     `category`, `doc_title`, `section`, product title; underscores→spaces + title-case.
  2. Add `display_label: str` to the `Citation` model; set it in `build_sources()` for
     both the SQL citation and each hit citation, alongside the unchanged `label`.
  3. Mirror the field in `frontend/src/api/types.ts` `Citation` (add `display_label: string;`).
- Files to touch: `backend/agents/composer.py`, `frontend/src/api/types.ts`.
  (Confirm `backend/app/main.py` needs no edit — `QueryResponse` extends `AnswerResult`.)
- Integration point: the chip in M8v4.4 binds to this field; the LLM prompt/extractive
  text keep using `label`, so answer composition is unchanged.

### M8v4.2 Remove operator instrumentation
- Goal: strip the pipeline-diagnostic surface the i3 build exposed.
- Acceptance criteria:
  - [ ] `SessionCard` (Cost/Tokens/Latency/Thread/User/Provider) and its `RoleRail` slot
        are gone; `TrustStrip` (route/grounded/latency/cost pills, `why ▾`, fallback
        note, expanded tool-path/tokens/cost/memory/SQL body) is gone — not replaced by a
        "grounded" badge; the `ScopeCard` technical flags are gone.
  - [ ] Forbidden-surface count 0 for the tokens these components rendered.
- Build steps:
  1. Delete `SessionCard.tsx` and `TrustStrip.tsx`; remove their imports/mounts.
  2. In `RoleRail.tsx` remove the `SessionCard` slot; remove `TrustStrip` from the
     assistant turn (`AssistantTurn.tsx`).
  3. Retire the technical `ScopeCard` presentation (its `audit.scope` data source is
     reused by the plain scope line in M8v4.5); keep no `restricted`/slug/"filtered" text.
- Files to touch: `frontend/src/components/SessionCard.tsx` (delete),
  `TrustStrip.tsx` (delete), `RoleRail.tsx`, `AssistantTurn.tsx`, `ScopeCard.tsx`.
- Integration point: rail and turn still render; scope line re-added in M8v4.5.

### M8v4.3 Copy + brand + header re-word
- Goal: plain-language brand line, header, and honest-state strings.
- Acceptance criteria:
  - [ ] `BrandCard` tagline is `grounded · cited` (no `$0/query`).
  - [ ] `ConversationPanel` header shows an `answering as: <role>` pill (role from
        `audit.role`/active identity), no `· <intent>`.
  - [ ] `copy.ts`: `FALLBACK_NOTE` → "Here are the exact words from the sources:";
        `SQL_DEGRADED` → "We couldn't calculate the numbers for this one — here's what
        customers actually said:"; `NO_EVIDENCE` → "I couldn't find anything about that
        in the sources you have access to. Try rephrasing, or ask about a different
        product or topic."; `STAGES` removed; a system-error string added; `startersFor`
        kept; `evidenceType` kept only if used internally (never shown as a tag).
- Build steps:
  1. Edit `BrandCard.tsx` tagline.
  2. Edit `ConversationPanel.tsx` (+ the `meta` wiring in `App.tsx`) to the role-only pill.
  3. Re-author strings in `copy.ts`; remove `STAGES`; add the system-error string.
- Files to touch: `frontend/src/components/BrandCard.tsx`, `ConversationPanel.tsx`,
  `App.tsx`, `frontend/src/copy.ts`.
- Integration point: strings consumed by the honest states (M8v4.5) and the header.

### M8v4.4 Source chips + evidence panel (bound to `display_label`)
- Goal: render citations as readable source chips feeding the one-at-a-time evidence view.
- Acceptance criteria:
  - [ ] Chips render `Source: <display_label>` (not `[n]` + `source_id`, not `label`);
        are real `<button>`s; one active at a time across the thread; active state is
        conveyed non-colour-only (text/weight); keyboard-reachable with focus rings.
  - [ ] `EvidencePanel` shows one source: readable title (`display_label`) + redacted
        `snippet`; no raw `source_id`/`eid` line, no mono type tag. Empty prompt →
        "Tap a Source on any answer to read the exact words it came from."; `null`
        snippet → "the exact words aren't available to show."
  - [ ] Phone evidence bottom-sheet: open moves focus in, Escape + backdrop close and
        return focus to the chip.
- Build steps:
  1. Rework `CitationChips.tsx` to render `Source: {c.display_label}` and keep
     click-to-inspect / active highlighting (keyed by `n`/`source_id`, never displayed).
  2. Rework `EvidencePanel.tsx` copy + item to title + redacted snippet, with the two
     empty/null strings; keep the bottom-sheet + focus/Escape behaviour.
- Files to touch: `frontend/src/components/CitationChips.tsx`, `EvidencePanel.tsx`
  (plus `App.css` for the chip/dock styling to match the mockup).
- Integration point: consumes `display_label` from M8v4.1; wired into the existing
  active-citation state in `App.tsx`.

### M8v4.5 Identity switcher demo framing, remaining states, styling
- Goal: finish the surface — demo switcher, empty/loading/nothing-found/system-error
  states, scope line, and styling to match the mockup.
- Acceptance criteria:
  - [ ] `IdentitySwitcher` options read `user_id (<team> team)` (e.g. "support_1 (support
        team)"); set apart as demo (dashed border, "⚙ demo — not a login" tag, the
        not-part-of-the-product note); switching reloads owner-scoped history and resets
        to that owner's empty state; accessible `<select>` name; "demo — not a login"
        is textual, not colour-only.
  - [ ] Empty state: brand logo, plain tagline, derived scope line
        (`scopeLine(audit.scope)` / `scope_for_role`), 2 role starters — no metrics/intent.
  - [ ] Loading: question echoed + "Looking through the sources…" + spinner, composer
        disabled, **no STAGES pipeline**; reduced-motion disables the spinner.
  - [ ] Nothing-found and System-error states render the plain strings (system error
        shows a **Try again** button and never the HTTP status/`detail`/provider/trace).
  - [ ] Transcript is a fixed-height scrollable region, auto-scrolled to newest; charts
        still gated on `"sql" ∈ audit.sources[]`; `aria-live="polite"` on the stream;
        active history row is a `<button>` with `aria-current="true"`.
  - [ ] Forbidden-surface count 0 across all these states.
- Build steps:
  1. Update `IdentitySwitcher.tsx` labels + demo styling + the owner-scoped reset.
  2. Update `EmptyState.tsx` (copy + scope line), `LoadingState.tsx` (drop stages).
  3. Add the system-error render path (consume the new copy string) in the turn/error
     component; keep `nothing-found` plain.
  4. Apply `App.css` styling to match the mockup (bounded `.stream`, chips, evidence
     dock/sheet, demo card, honest-state blocks).
- Files to touch: `frontend/src/components/IdentitySwitcher.tsx`, `EmptyState.tsx`,
  `LoadingState.tsx`, `ErrorBanner.tsx`/`AssistantTurn.tsx` (system-error path),
  `ScopeCard.tsx` or `ScopeRibbon.tsx` (plain scope line), `App.tsx`, `App.css`.
- Integration point: ties together chips (M8v4.4), copy (M8v4.3), and the decluttered
  rail (M8v4.2) into the full mockup-matching surface.

## Test plan
- **M8v4.1 (scoped):** one backend test file (e.g. `backend/tests/test_composer_display_label.py`)
  asserting `display_label` per source type (review/doc/SQL), no raw ASIN/id/slug in it,
  and `label`/`snippet` unchanged. Tester runs this one file + one smoke, never the full suite.
- **M8v4.2–.5 (scoped):** per sub-module, a frontend DOM/unit check (Vitest/RTL) that the
  named elements render/are absent and the forbidden tokens count 0 for that block;
  chip active-state + evidence open/close; empty/loading/nothing-found/system-error renders.
- **Module-level end-to-end smoke (free mode, $0):** boot backend in free mode, run a live
  `POST /query` for "What is the return policy?" → assert a grounded, cited answer whose
  `citations[].display_label` is human-readable (no raw id/ASIN/slug); then the vague
  follow-up "And what about opened electronics?" → cited answer; assert forbidden-surface
  DOM count is 0 across both turns and both show readable source chips whose click reveals
  a redacted snippet.

## Security & cost notes
- **Cost: $0** — free mode, no cloud spend; **no cost gate triggered** (CHECKPOINT 1 is
  spec approval only).
- No secrets touched. `display_label` is PII-safe by construction (derived from
  category / product title / document title only — no raw review or user text); the
  redacted `snippet` remains the only place verbatim source text appears.
- Governance unchanged: scope enforced server-side at retrieval; UI never widens scope;
  category names never hard-coded; charts gated on `"sql" ∈ audit.sources[]`.

## Out of scope
- B-15 (vague-follow-up routing) and B-16 (audit user_id/evidence enrichment).
- Any pipeline / retrieval / governance / memory change; `GET /threads` endpoints.
- Restored-turn persisted citations (needs per-turn `citations` persisted — open backend
  change, flagged in handoff §3.1, not built here).
- Any second backend field beyond `citations[].display_label`.

## Authorized answer-quality presentation localization (2026-11-03)

User explicitly authorized fixing known answer-quality defects; see
`M4_answer_quality_stage4_workaround.md`. This supersedes the earlier backend-field
limit only for additive optional `citations[].passage` and grounding path `calculated`.
Use one safe Markdown/citation renderer for live/replay, optional expandable redacted
passages, and dimension-validated SQL comparisons/time series independent of role.
Ambiguous/incomplete results stay tables. No raw HTML execution or unsafe generated
links. Existing owner/history/governance contracts and layout remain in place.

Authorized conversational correction (2026-11-03): see
`M4_conversational_planning.md` for pre-routing interpretation, typed clarification
state, large-tier synthesis and additive permission-filtered suggestion fields.

### Current answer-quality response/UI integration (2026-11-03)

Optional `suggestions`, `clarification_state` and `conversation_state` extend the
response and existing JSON render snapshots, not database schema. Suggested
questions reflect the active validated plan/result and role. Buttons fill/focus
the composer, never auto-submit; restored turns retain choices. Specific backend
zero-match/failure text must not be replaced with generic no-evidence copy.
`citations[].passage` supports full redacted expandable context. Shared safe
Markdown/grouped-citation rendering applies to live/history and every role shape;
charts require complete, dimension-compatible results. Historical layout/spec
restrictions apply except where these authorized appendices explicitly extend them.
