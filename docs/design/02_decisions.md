# 02 · Design Decision Log — M8 Chat / Serving UI

**Design Track · iteration 2 · Stage 4 (decision log).** Written after the hi-fi
mockup (`mockups/m8-chat.html`) was approved at CHECKPOINT D2. This is the "why"
record for a reviewer: each decision, the alternative it beat, and the rationale.
Paired with `03_handoff.md` (the build spec). No application code is changed by
this document.

> **Honest framing.** v1 (M1–M8) was an engineering spike built first — it proved
> the governed agentic-RAG pipeline end-to-end at $0 with a deliberately minimal
> chat UI. This track is SDLC iteration 2: a design-driven redo of the *UI
> surface* on top of that working system. Every decision below is about rendering
> the backend's existing `audit` record well, not about changing the pipeline.

---

## 1. Decision log

### 1.1 Information architecture & trust surface

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D-01 | **Docked Evidence panel** (right column; bottom-sheet on phone) for inspecting citations. | A persistent full-audit sidebar always showing every `audit` field. | A standing audit sidebar reads as a developer console and buries the answer — it would repeat v1's failure in the opposite direction (too much, undifferentiated). A dock that opens *on citation click* keeps evidence one gesture away without competing with the answer. Citations need room to show label + id + snippet and to cross-reference, which a growing bubble can't give. |
| D-02 | **Per-turn inline trust strip** with a collapsed header (`route · grounding · latency · $0`) and a one-click **"why ▾"** reveal of the full reasoning. | A modal dialog, a separate "details" route, or a hover tooltip. | Satisfies brief criterion 1 ("why-this-answer in one action"): the header is always visible so trust is *glanceable*, and a single click expands `intent`, `tool_path`, `grounding.path`, `sources`, tokens/cost/latency, memory. Trust lives **with the claim it explains**, per turn — not in a global panel detached from the answer. A modal hides the answer; a tooltip can't hold this much structured detail accessibly. |
| D-03 | **Trust strip and Evidence panel are separate affordances.** Strip = the "how" (reasoning/audit); panel = the "what" (evidence bodies). | Fold evidence into the expanded trust strip. | They answer different questions and have different space needs. The strip is compact, per-turn, metadata-shaped; evidence is longer-form, scannable, cross-referenced by `[n]`. Separating them keeps each legible and maps cleanly to two criteria (1 = reasoning, 2 = evidence). |

### 1.2 Role-adaptive rendering

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D-04 | **Three role-adaptive answer shapes** chosen by `role` + `audit.intent`: support = issue/fix rows + governing-policy card; marketing = theme bars + sentiment trend; executive = headline + ranked-metric bars + one-line cause. | One uniform answer-text renderer for all roles (what v1 does). | The three PRD §2 personas walk up with genuinely different jobs; the *same* API answer serves all three but the useful *shape* differs. Role→render difference is brief criterion 4 and is demonstrable by switching persona on comparable questions. The shape is a presentation choice over the same grounded, cited answer — no new data is introduced. |
| D-05 | **Charts/metric strips are gated on evidence actually present** — a trend/ranked strip renders only when `"sql"` is in `audit.sources[]`. | Always draw a chart for analytics roles. | Design must not outrun governance (brief §5). A chart is a view of the *same M6-scoped retrieval* that produced the answer; it must never imply data the response didn't carry. If the SQL leg degraded (no `"sql"` source), the chart is suppressed, not faked. |
| D-06 | **Role selection is a persona picker populated from `GET /roles`**, defaulting to the three PRD drivers (support/marketing/executive); `admin`/`analyst` are secondary. | Hard-code three personas, or expose all roles equally. | `GET /roles` is the single source of truth for valid roles (sending an unknown role is the documented 400). The PRD personas drive the shape templates; admin/analyst fall back to a default shape. Hard-coding would drift from `ACCESS_POLICY`. |

### 1.3 Scope / governance legibility

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D-07 | **Scope is shown as a read-only fact, never a control.** A scoped persona sees a rail card + an inline answer ribbon stating evidence was filtered to their categories *at retrieval, before the model*; executive sees the complementary "unrestricted" note. | A "show all categories" toggle / scope filter the user can widen. | Access policy is enforced server-side at retrieval (M6, security.md). The UI must never offer a path around it (brief §5). A toggle would imply the client can widen scope — it cannot, and designing one invites a governance bug. Framing is deliberate: "the search was scoped," never "the model hid data." |
| D-08 | **Scope copy states *that* a filter applies (derived from role) but does not enumerate category names** in the shipped data path. | Hard-code the category lists from `ACCESS_POLICY` into the frontend. | Category names are not in the response contract today (see Pending field #2). Hard-coding them client-side would duplicate governance config in the UI and silently rot when the policy changes — a correctness and security smell. The mockup shows illustrative chips flagged as pending; the real build states the fact and enumerates only once a `scope` field exists. |

### 1.4 States & honesty

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D-09 | **Every state is a designed screen:** empty, loading, grounded, role-scoped, graceful-degradation (`sql_error`, `grounding.path=="none"`), fallback (`llm draft blocked`→extractive), and error. | Reuse one answer renderer and let absent data render blank (v1). | Brief criterion 5. v1 had no distinct states — empty, loading, degraded, and error were blank or identical. A reference build should show the pipeline's real behaviours, especially the graceful ones. |
| D-10 | **Degradation is a designed answer, not an error.** `sql_error` → amber warn-line + the RAG answer still renders/cites, metric strip suppressed. `grounding.path=="none"` → calm "no supporting evidence" block, no red banner. | Treat any degradation as an error banner. | These are honest, *successful* `200` responses where the pipeline degraded gracefully (SQL failed but RAG grounded; or nothing matched in scope). Painting them red would misrepresent a working system and scare the user. Red is reserved for HTTP failures (D-11). |
| D-11 | **Distinguish 400 from 502.** 400 (unknown role / `AccessDenied`) = amber "your input" banner → *reselect role*, no retry. 502 (`PipelineError`) = red "our pipeline" banner → *retry* same query + copy details. A bare 500 maps to the 502 treatment. | One generic error banner for all failures (v1). | Brief criterion 5. The fix differs: an invalid role won't be fixed by retrying; an upstream blip will. Routing the user to the right action requires distinguishing the status. The user's question is preserved in both so nothing is lost. Status/`detail` come straight from `ApiError` (client.ts). |
| D-12 | **Loading is a generic staged simulation**, not live telemetry: labels "routing → retrieving (scoped) → grounding → answer" describe the known pipeline shape. | A live progress stream reading `tool_path` as it happens. | The backend returns **once**, not as a stream (PRD §5 non-goal; brief §5). `audit.tool_path` is unknown until the response lands, so the loading copy must read as a generic hint, never as a claim about *this* turn. Honest within the non-streaming constraint. |
| D-13 | **Surface $0 cost + latency as an honest headline property**, not a buried metric: brand line "grounded · cited · $0/query", a session card with `cost_usd`/`tokens`/`latency_ms`, and a cost pill on every trust strip. | Hide cost/latency as internal telemetry. | Brief criterion 6. $0/query (free-provider mode) and low latency are true, distinctive properties of this build; showing them is honesty, not marketing. The `$0` is a real consequence of free mode (`audit.cost_usd`), labelled as a per-turn fact — provider mode itself stays invisible (brief §5). |
| D-14 | **Theme-aware (light + dark) via tokens**, 16px gutter, works at phone width (columns stack, Evidence panel → bottom sheet). | Single fixed theme, desktop-only layout. | Artifact page contract (tokens for both schemes, 16px gutter, no horizontal scroll at phone width). Honoring `prefers-color-scheme` with an explicit toggle override is table stakes for a portfolio-grade surface. |
| D-15 | **Memory shown as a read-only audit line** ("used N prior turns · persisted M") inside the expanded strip, not as a visible conversation history or thread list. | Build a multi-turn conversation list / thread switcher UI. | Memory exists in the backend (`audit.memory`) and is worth *showing as a fact*, but a full multi-turn history UI is out of scope for this iteration (see §2). Round-tripping `thread_id`/`user_id` keeps the plumbing correct; the UI just reports what memory did. |

---

## 2. Deferred / where we stopped and why

These are **conscious stops for a reference build**, not accidental omissions.
Each is safe to defer because the backend already behaves correctly; only the UI
surface is deliberately narrowed.

| Deferred item | Why stopped here | What a later pass would add |
|---|---|---|
| **Multi-turn thread history & conversation list.** | The design renders a single Q→A turn. Memory *works* server-side and is round-tripped (`thread_id`/`user_id`) and *reported* (D-15), but there is no rendered history, no thread switcher, no "new conversation". One turn is enough to prove every state and shape; a thread UI is a separable feature. | A scrollable multi-turn thread, a conversation list keyed by `thread_id`, "new chat", and per-turn memory indicators. The data (`audit.memory.history_turns_used`) is already there. |
| **Streaming / token-by-token rendering.** | PRD §5 non-goal. The backend returns once; the loading state is a generic staged simulation (D-12). Designing a stream would misrepresent the contract. | A streaming transport + an answer that fills progressively, with `tool_path` stages lit as they actually occur. |
| **Authentication / identity.** | Out of scope this iteration (brief §5, PRD §3). Role is a self-selected persona picker; `user_id` is a local anonymous id (v1 stores it in `localStorage`). No login, no session trust boundary. | Real auth, server-asserted role (not client-chosen), and scope derived from the authenticated identity rather than a picker. |
| **The 3 pending backend fields** (see `03_handoff.md` §Pending). | The UI must not fabricate data the response doesn't carry (brief §5). Citation snippet bodies, enumerable scope categories, and a source-type tag are shown as *mock/illustrative and flagged* in the mockup rather than invented. | Backend adds `citations[].snippet` (or a documented derivation), a `scope`/categories field (or `GET /roles` extension), and optionally `citations[].source_type`. Until then the UI states the fact without the detail. |
| **Session-card figures reused across scenarios.** | In the mockup the per-persona canned `audit` numbers (tokens/cost/latency) are reused across scenarios for demonstration. This is a *mockup* convenience, not a design claim. | In the real build every figure binds live to that turn's `audit`; no reuse. The handoff names the exact bindings so this is unambiguous. |
| **Admin / analyst bespoke shapes.** | Not PRD §2 personas (brief §2). They are valid roles (unrestricted) but render with a sensible default shape rather than a tailored template. | Dedicated templates if those roles become product drivers. |
| **Evidence panel richness** (highlighting the cited span inside a longer source, source previews, external links). | Blocked on the snippet field; current design shows label + `source_id` + (pending) snippet. | Span highlighting, document preview, and deep links once the backend returns enough evidence body. |

---

*Paired with: `03_handoff.md` (the build spec the Developer implements).
Sources: `00_brief.md`, `01_wireframes.md`, `mockups/m8-chat.html` (approved D2),
and the real contract in `backend/app/main.py`, `agents/pipeline.py`,
`agents/composer.py`.*
