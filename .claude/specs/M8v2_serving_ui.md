# Spec M8 v2: Serving & UI — design-driven rebuild

> **Iteration 2, not a fresh build.** M8 is DONE as v1 (engineering spike: minimal
> React/Vite chat in `frontend/src/{App.tsx, components/*, api/*}`). This spec
> rebuilds the **UI surface** on top of the unchanged backend pipeline, driven by
> the approved Design Track package (`docs/design/03_handoff.md` is authoritative;
> `02_decisions.md` is the rationale; `mockups/m8-chat.html` is the visual
> reference). Backend changes are limited to two small, additive, backward-
> compatible contract edges (§M8v2.1). The v1 spec `.claude/specs/M8_serving_ui.md`
> is left intact.

## User story
As a retail business user (support, marketing, executive — plus admin/analyst), I
want a trustworthy, role-adaptive chat that shows *why* each answer is grounded,
*what* evidence it used, and *that* my access was scoped — so that I can rely on a
cited answer and see the governance working, without the UI ever being able to
widen my scope.

## Module acceptance criteria
- [ ] The backend returns two new, additive fields with no change to existing
      behaviour: `citations[].snippet: string | null` (the source text, trimmed to
      `MAX_QUOTE_CHARS` and run through `governance.pii.redact()`), and
      `audit.scope = {restricted: bool, categories: string[]}` derived from the
      retrieval scope actually used. Old consumers keep working (purely additive).
- [ ] **PII regression guard:** no raw source text reaches the client. Every
      `citations[].snippet` is `redact()`-ed at the composer boundary (same scrub
      the answer and audit-stored query already get); a test proves an email/phone
      in source text becomes `[EMAIL]`/`[PHONE]` in the snippet.
- [ ] **Marketing-scope regression guard:** `ACCESS_POLICY["marketing"]` stays
      `{Electronics, Beauty_and_Personal_Care, Toys_and_Games}` (ADR 2026-10-28,
      Books dropped). M8 v2 does not change or regress it; all scope-related UI
      copy/behaviour is consistent with it.
- [ ] **No hard-coded category chips:** the frontend contains zero literal category
      lists. Scope chips render **only** from `audit.scope.categories`; when that is
      empty/absent the UI states *that* a scope applies (from role) without naming
      categories. Scope is read-only — no control, toggle, or param can widen it.
- [ ] The rebuilt SPA renders the handoff state machine (§2): empty, loading,
      grounded, fallback, degraded-SQL, no-evidence, 400, 502 — each a distinct
      designed screen, never a blank or a single generic error.
- [ ] Three role-adaptive answer shapes (§4: support / marketing / executive;
      default for admin/analyst), inline `[n]` markers + citation chips, a per-turn
      trust strip (collapsed header + "why ▾" expand of full `audit`), and a docked
      Evidence panel (bottom-sheet on phone) bound to the real fields in §3.
- [ ] Accessibility contract (handoff §5) met: `:focus-visible` rings, `aria-expanded`
      on the trust toggle, `aria-live="polite"` stream, `role="alert"` banners,
      labelled charts, `prefers-reduced-motion`, keyboard paths, light/dark tokens.
- [ ] `npm run build` (typecheck + vite build) passes; backend contract test file
      passes; one real end-to-end smoke renders a grounded, cited answer. Cost $0.
- [ ] **Visual fidelity (ADR 2026-10-28, via `/change`):** the SPA realizes the D2
      mockup (`docs/design/mockups/m8-chat.html`) as its **visual contract** — its full
      design-token set, type scale, spacing, shadows/radius, and the card/chat/
      evidence/chart/trust/state styling — in both light and dark, at desktop and phone
      widths. The mockup's stylesheet is ported as `App.css` and each affected component's
      markup conforms to the mockup's DOM. This is a **restyle only**: no change to
      behaviour, data bindings, the state machine, or the governance guards — scope chips
      still render only from `audit.scope.categories` (zero hard-coded category literals),
      snippets stay `redact()`-ed, scope stays read-only.
- [ ] **Browser visual-QA (new gate):** with the app running at `localhost:5173`, drive
      each role (support/marketing/executive/default) across each state (empty, loading,
      grounded, fallback, degraded-SQL, no-evidence, 400, 502) in light **and** dark at
      desktop + phone widths, and confirm each matches the mockup before marking done
      (closes the "no browser visual check ran" gap logged in the v1 note).

## Sub-modules (ordered, each build → verify → integrate)

### M8v2.1 Backend contract edges (snippet [redacted] + audit.scope)
- Goal: give the frontend real fields to bind to — add the evidence snippet and the
  scope descriptor, additively, with the pipeline otherwise unchanged.
- Acceptance criteria (trace: handoff §0, Pending #1 & #2):
  - [ ] `Citation` gains `snippet: str | None`; `build_sources()` sets it from the
        tuple text half as `redact(" ".join(text.split())[:MAX_QUOTE_CHARS])` (the
        same trim `_extractive()` uses). `None` only if there is no source text.
  - [ ] `audit["scope"] = {"restricted": bool(cats), "categories": cats}` where
        `cats = list(decision.scope.get("category", []))` — the scope retrieval
        actually used; `restricted=False, categories=[]` for unrestricted roles.
  - [ ] A PII test proves an email/phone embedded in source text is redacted in
        `snippet`; a scope test proves marketing → the three allowed categories and
        executive → `restricted=False, categories=[]`.
- Build steps:
  1. `composer.py`: add `snippet: str | None = None` to `Citation`; in
     `build_sources()` compute the redacted, trimmed snippet for both the SQL row
     (`_sql_text`) and each hit (`hit.chunk.text`) and pass it on the `Citation`.
     Import of `redact` already exists. Do not change answer text or grounding.
  2. `pipeline.py`: in the `result.audit.update(...)` block, add `scope` derived
     from `decision.scope`. (Optional helper `categories_for_role(role)` in
     `policy.py` only if needed for the error/pre-decision path — otherwise derive
     from `decision.scope` which is truer.)
  3. Keep everything else byte-for-byte: `main.py`, routing, memory, SQL, grounding.
- Files to touch: `backend/agents/composer.py`, `backend/agents/pipeline.py`
  (optional `backend/governance/policy.py` helper), new
  `backend/tests/test_contract_edges_m8v2.py`.
- Integration point: additive to the M6 composer/pipeline output that `/query`
  already returns; `QueryResponse` picks the new fields up automatically via
  `AnswerResult`.

### M8v2.2 API layer update (types + client reflect the new fields)
- Goal: mirror the extended contract in TypeScript so the UI binds to reality.
- Acceptance criteria (trace: handoff §0, §3):
  - [ ] `Citation` adds `snippet: string | null`; a typed `Audit` interface models
        the real keys (`query, role, intent, tool_path, sources, tokens, cost_usd,
        latency_ms, grounding{path,issues}, sql_error?, memory?, scope{restricted,
        categories}`); `QueryResponse` uses `Audit` (not `Record<string,unknown>`).
  - [ ] `client.ts` is unchanged except types; `ApiError{status,detail}` preserved.
  - [ ] `npm run typecheck` passes.
- Build steps: update `types.ts` (add `snippet`, add `Audit`, `Grounding`, `Scope`,
  `Memory` interfaces); confirm `getRoles()`/`postQuery()` still compile.
- Files to touch: `frontend/src/api/types.ts` (edit), `frontend/src/api/client.ts`
  (only if a type import changes). Reuse v1's `BASE_URL`/`ApiError` as-is.
- Integration point: consumed by all later frontend sub-modules; calls the live
  M8v2.1 backend.

### M8v2.3 App shell + state machine + role rail
- Goal: the 3-column responsive shell, theme, and the governance-legible left rail.
- Acceptance criteria (trace: handoff §1 rail/brand/role/scope/session, §2 composer,
  D-06/07/13/14):
  - [ ] 3-column grid `236px | 1fr | 300px`; collapses to 2 cols `<1080px`
        (Evidence → bottom sheet) and 1 col `<760px` (rail → top bar), 16px gutter,
        no horizontal scroll at phone width.
  - [ ] Role picker populated from `GET /roles`, default-selected to a PRD persona;
        selection drives `req.role`. Theme toggle overrides `prefers-color-scheme`
        via `data-theme`; both schemes meet WCAG AA.
  - [ ] Scope card is **read-only**: states scoped-vs-unrestricted from the role;
        renders category chips **only** from `audit.scope.categories` after a
        response (none before/when empty) — zero hard-coded category names.
  - [ ] Session card binds live per-turn `cost_usd`/`tokens`/`latency_ms` +
        `thread_id`/`user_id` (round-tripped), plus a static "Provider: invisible"
        line. A central state machine holds one active panel state (§2).
- Build steps: rewrite `App.tsx` as the shell owning the state machine and
  `user_id`/`thread_id` round-trip (reuse v1 `localStorage` user-id); add
  `components/RoleRail.tsx`, `BrandCard.tsx`, `ScopeCard.tsx`, `SessionCard.tsx`,
  `ThemeToggle.tsx`; replace `App.css` with a token-based light/dark stylesheet.
- Files to touch: `frontend/src/App.tsx` (rewrite), new rail components + theme CSS.
  Reuse `main.tsx`, `vite.config.ts`, `vite-env.d.ts` unchanged.
- Integration point: imports the M8v2.2 client/types; hosts the panel built next.

### M8v2.4 Conversation panel + role-adaptive answer shapes + trust strip
- Goal: the center column — the answer, its three shapes, citations, and the "why".
- Acceptance criteria (trace: handoff §1 conversation, §4, §3 answer/trust bindings,
  D-02/03/04/05):
  - [ ] Answer body parses `R.answer` by line; `[n]` tokens become real `<button>`
        inline markers (`aria-label="Show evidence n"`) that open the Evidence panel.
  - [ ] Template selected by `role` + `audit.intent`: support = issue/fix rows +
        governing-policy card (doc citation); marketing = theme bars + "from SQL"
        trend; executive = headline + ranked-metric bars + one-line cause; unknown
        role/intent → default plain-claim shape (never errors). Charts render **only
        if** `"sql" ∈ audit.sources` (suppressed otherwise, never fabricated).
  - [ ] Citation chips (one per `citations[]`: `[n] label`) open Evidence; scope
        ribbon restates in-scope-vs-all-categories from the role.
  - [ ] Trust strip: collapsed header (`intent · grounding.path · latency_ms · $0`)
        with `aria-expanded`; "why ▾" expands full audit (tool_path joined, grounding
        explain, sources count+ids, tokens, memory line, sql_error/issues when
        present). Same answer/evidence across shapes (presentation only).
- Build steps: add `components/ConversationPanel.tsx`, `UserTurn.tsx`,
  `AssistantTurn.tsx`, shape templates (`shapes/SupportShape.tsx`,
  `MarketingShape.tsx`, `ExecutiveShape.tsx`, `DefaultShape.tsx`), `ScopeRibbon.tsx`,
  `CitationChips.tsx`, `TrustStrip.tsx`, and an `answer.ts` util that splits lines /
  parses `[n]`. Charts use labelled `<svg role="img" aria-label="…">`.
- Files to touch: new center-column components + `answer.ts`. Remove v1
  `components/MessageList.tsx` and `components/Citations.tsx` (superseded).
- Integration point: rendered inside the M8v2.3 shell for the `grounded`/`fallback`/
  `degraded-SQL`/`no-evidence` states; chips/markers call into M8v2.5's panel.

### M8v2.5 Evidence panel / bottom-sheet + all states + accessibility
- Goal: evidence inspection, every non-grounded state, and the a11y contract.
- Acceptance criteria (trace: handoff §2 states, §3 evidence bindings, §5, D-01/
  09/10/11/15, Pending #3/#4):
  - [ ] Evidence panel (right dock; bottom-sheet `<1080px`) lists the active turn's
        `citations[]`: `[n]` + `label` + `source_id` + **redacted** `snippet` (from
        M8v2.1; if `snippet` null on the llm path, show label+id with no quote — do
        not fabricate). Type tag is UI-derived from `source_id`/`label` (Pending #3).
        Clicked chip highlights + scrolls its item in; empty when nothing clicked.
  - [ ] States wired: `empty` (role-conditioned authored starters), `loading`
        (staged generic labels + Cancel, composer disabled, no audit shown),
        `no-evidence` (calm block, not red), `degraded-SQL` (amber warn-line, metric
        strip suppressed, `sql_error` in expanded strip), `fallback` (issues note),
        `400` (amber, reselect-role, no retry), `502/500` (red, retry + copy),
        preserving the user turn. Degradation copy authored from field presence.
  - [ ] A11y: `:focus-visible` rings on all interactive elements; `aria-expanded`
        on trust toggle; `aria-live="polite"` on the stream; `role="alert"` on
        banners; `prefers-reduced-motion` disables shimmer/transitions; Enter
        submits, Escape closes sheet, focus moves into sheet on open and returns to
        the trigger on close; charts carry `aria-label`.
- Build steps: add `components/EvidencePanel.tsx` (+ bottom-sheet behaviour),
  `ErrorBanner.tsx`, `EmptyState.tsx`, `LoadingState.tsx`; author
  `starters.ts`/`copy.ts` for role-conditioned prompts and degradation sentences;
  finalize focus management and reduced-motion in the theme CSS.
- Files to touch: new state/evidence components + copy modules; theme CSS additions.
- Integration point: completes the M8v2.3 state machine and consumes M8v2.4's
  citation-click handler; closes the module.

## Test plan
- **M8v2.1** (tester, scoped): run `backend/tests/test_contract_edges_m8v2.py` only
  (not the full suite — it hangs on torch downloads). Asserts snippet redaction
  (email/phone → `[EMAIL]`/`[PHONE]`), snippet trim ≤ `MAX_QUOTE_CHARS`, and
  `audit.scope` shape for marketing (3 categories) vs executive (unrestricted).
- **M8v2.2**: `npm run typecheck` passes against the extended contract.
- **M8v2.3 / .4 / .5**: `npm run build` passes after each; per-sub-module scripted/
  manual check of the added surface (rail+scope-from-field; shapes+trust expand;
  states+evidence snippet+a11y). No JS unit runner (build+typecheck is the gate,
  per v1 convention).
- **Visual-fidelity `/change` (ADR 2026-10-28)**: after the restyle, `npm run build`
  still passes (typecheck proves no binding/structure regression), and two grep guards
  hold — the frontend contains zero literal category names, and no raw (un-`redact`-ed)
  snippet path was introduced. Then a **browser visual-QA** pass (below) is the gate that
  proves the restyle matched the mockup without drifting behaviour. The restyle touches
  presentation only; no new tester unit is added beyond re-running the build + guards.
- **Browser visual-QA** (visual-fidelity `/change`): launch backend `PROVIDER_MODE=free`
  + `npm run dev`, open `localhost:5173`, and compare to the mockup for each role
  (support/marketing/executive/default) × each state (empty, loading, grounded, fallback,
  degraded-SQL, no-evidence, 400, 502) in light **and** dark at desktop + phone widths.
  Confirm tokens/type/spacing/shadows, the three answer shapes, the trust strip collapsed
  + expanded, the Evidence panel (dock + bottom-sheet), and no horizontal scroll at phone
  width. If the browser cannot be driven, the tester reports that plainly — not a silent PASS.
- **Module end-to-end smoke** (one real run, per `.claude/rules/testing.md`): backend
  `PROVIDER_MODE=free` (`uvicorn app.main:app`) + `npm run dev`; as support, marketing,
  and executive, ask one real question each and confirm a grounded, cited answer in
  the correct shape, a redacted snippet in the Evidence panel, scope chips sourced
  from `audit.scope`, the trust strip expanding the real audit, and a degraded/
  no-evidence case rendering as a calm (non-red) state. If the live LLM/DB path is
  unavailable, the tester reports it plainly — not a silent PASS.

## Security & cost notes
- **Cost: $0.** Free provider mode, no cloud provisioning, no embedding/cluster runs.
  Deployment stays INERT as in v1 (reuse existing Dockerfiles / inert Bicep; not
  re-planned here). No cap needed since nothing provisions. CHECKPOINT 1 is also the
  (nil) cost go-ahead.
- **PII:** new `snippet` is `redact()`-ed at the composer boundary; no raw source
  text reaches the client. Secrets unchanged (`.env`; `VITE_API_BASE_URL` documented).
- **Access control stays server-side at retrieval, before the LLM.** The UI only
  *selects* a role; it has no path to widen scope. Scope chips derive from
  `audit.scope` (what retrieval used), never from client-side category literals.
  Marketing scope is a regression guard, unchanged by this module.

## Out of scope (handoff §6 / 02_decisions §2)
- Streaming / token-by-token rendering (backend returns once; loading is simulated).
- Authentication / identity (role is a self-selected persona; `user_id` is a local
  anonymous id).
- Multi-turn history UI / conversation list / thread switcher (single Q→A rendered;
  `thread_id`/`user_id` round-tripped and memory *reported* via `audit.memory` only).
- Enumerating scope categories from any client-side list (only `audit.scope`).
- Any further backend/pipeline change beyond the two additive edges in M8v2.1;
  `citations[].source_type` stays UI-derived (optional future backend nicety).
- Live Azure provisioning/deploy, TLS, custom domains.

---
**CHECKPOINT 1 report (for the orchestrator):**
- Spec: `.claude/specs/M8v2_serving_ui.md`
- Sub-modules: M8v2.1 backend edges (snippet[redacted]+audit.scope) · M8v2.2 API
  types/client · M8v2.3 shell+state-machine+role rail · M8v2.4 conversation panel+3
  role shapes+trust strip · M8v2.5 Evidence panel+all states+a11y.
- 3-line summary: Design-driven rebuild of the M8 chat UI on the unchanged backend,
  per the approved handoff; two additive backend edges give real snippet+scope fields
  so the UI never fabricates data. Governance stays server-side; snippets are PII-
  redacted, scope chips come only from `audit.scope`, marketing scope is a regression
  guard. Delivers the full state machine, three role shapes, trust strip, and docked
  Evidence panel with the accessibility contract.
- Cost: **$0**, no cap needed (nothing provisions; deployment stays inert).
