# 00 · Design Brief — M8 Chat / Serving UI

**Design Track · iteration 2 · Stage D1 (brief).** Stops at CHECKPOINT D1 for
human approval. No wireframes, mockups, or application code yet — this document
fixes the *problem framing* only.

> **Honest framing.** v1 (modules M1–M8) was an **engineering spike**, built
> first and dated in `context/WORKLOG.md` and git history. It proved the
> agentic-RAG pipeline end-to-end at $0 with a deliberately minimal chat UI
> (M8.3: role picker, answer text, numbered citations, error banner). This track
> is **SDLC iteration 2**: a design-driven redo of the UI surface *on top of* a
> working system. Design did **not** come first, and this brief does not pretend
> it did.

---

## 1. Objective

The backend already answers hard questions well: a router picks the right tool
(SQL analytics, review-RAG, docs-RAG, or SQL+RAG), governance filters evidence
to the caller's role *before* the LLM sees it, and the composer returns a
grounded, cited answer plus a rich `audit` record describing exactly how the
answer was produced. The v1 UI renders the answer sentence and the citation
numbers — and discards almost everything else.

This redesign makes the copilot's **reasoning and trustworthiness visible**. A
non-technical retail user should be able to read an answer, see *why* it was
given, *what evidence* it rests on, and *that it stayed inside their access
scope* — without reading code or a log file. The design turns the existing
`audit` record from a hidden server artifact into the product's primary
trust surface, while never showing a role data its M6 scope forbids.

---

## 2. Personas & jobs-to-be-done (PRD §2)

The three personas and their representative questions are taken directly from
PRD §2. Their backend access scope is taken from `governance/policy.py`
(`ACCESS_POLICY`).

| Persona | Walks up with (PRD §2) | Job-to-be-done | Backend route | M6 scope |
|---|---|---|---|---|
| **Support agent** | "Is this headphone's disconnection a known issue, and the common fix?" | Resolve a customer case fast: find whether an issue is widely reported and what the documented fix / policy is, with a source they can trust and quote. | `review_rag`, `docs_rag` | **Scoped** — `Electronics, Home_and_Kitchen, Automotive, Pet_Supplies` |
| **Marketing / product** | "Top 3 complaints about our wireless earbuds this quarter — is sentiment improving?" | Understand *themes* in customer language and whether a *trend* is moving, to steer product and messaging. | `sql_rag` (themes via RAG + trend via SQL) | **Scoped** — `Beauty_and_Personal_Care, Toys_and_Games, Books` |
| **Executive** | "Which product categories have the worst rating-to-price ratio, and why?" | Get a defensible, numbers-first answer to a cross-category question, with a short explanation of the *why* — fit for a decision. | `sql_rag` (SQL quantifies, RAG explains) | **Unrestricted** (`{}`) |

Notes that shape the design:
- The three personas need **three different answer shapes** from the *same* API:
  support wants an evidence snippet + the governing policy; marketing wants a
  theme list beside a trend; executive wants a headline + a ranked metric with a
  one-line cause. One chat surface, role-adaptive rendering.
- Scope is a persona fact, not a toggle. Support and marketing are **category-
  scoped**; executive is unrestricted. The UI must make "you are seeing a
  filtered view" legible to the scoped personas without implying data is missing
  by accident.
- `ACCESS_POLICY` also contains `admin` and `analyst` (both unrestricted). They
  are not PRD §2 personas; treat them as secondary, not design drivers.

---

## 3. What v1's UI fails to show

The backend returns far more than v1 renders. `POST /query` returns a
`QueryResponse` = `answer` + `citations[]` + **`audit{}`** + `thread_id` +
`user_id`. v1 shows the `answer` and the citation numbers and **throws the rest
away**. The discarded signals, named from `agents/pipeline.py` and
`agents/composer.py`:

| Wasted signal (real field) | What it would tell the user | v1 |
|---|---|---|
| `audit.intent` | Which strategy answered: `sql` / `review_rag` / `docs_rag` / `sql_rag` | hidden |
| `audit.tool_path` (e.g. `["sql_agent","review_rag"]`) | The actual agent path taken — the "how" | hidden |
| `audit.grounding.path` (`llm` / `extractive` / `none`) | Whether the answer is model-written-and-checked, a verbatim extract, or unsupported | hidden |
| `audit.grounding.issues[]` | Why a draft was blocked (e.g. `"llm draft blocked"`, uncited claim) | hidden |
| `audit.sources[]` | The evidence IDs the answer rests on (`"sql"` + chunk ids) | only the count, as `[n]` markers |
| `audit.role` / scope | That retrieval was filtered to the caller's role *before* the LLM | hidden |
| `audit.cost_usd` | The $ cost of the turn (the project's headline: $0 in free mode) | hidden |
| `audit.tokens` | Token accounting for the turn | hidden |
| `audit.latency_ms` | How fast the governed pipeline answered | hidden |
| `audit.sql_error` (`"could not compute"`) | That SQL degraded gracefully and the answer leans on remaining evidence | hidden (silent) |
| `audit.memory.history_turns_used` / `persisted` | That this turn used conversation memory and what it kept | hidden |
| `citations[].label` / `.source_id` | Human-readable evidence (`"review B00… (Electronics)"`, `"Returns Policy / §3"`) and an inspectable id | number only; snippet not shown |

Beyond discarded fields, v1 has **no distinct states**: the empty first-run
state, the in-flight/loading state, the graceful-degradation state
(`sql_error`, or `grounding.path == "none"` → "no supporting evidence"), and the
role-scoped-answer state all look the same or are absent. The error banner
exists but does not distinguish a `400` (unknown role — input error) from a
`502` (upstream failure).

---

## 4. UX success criteria (checkable)

The redesign is "good" when a reviewer can verify each of these against the
mockup and, later, the built UI:

1. **Why-this-answer in one action.** From any answer, a user can reveal the
   route (`audit.intent`), the tool path (`audit.tool_path`), and the grounding
   status (`audit.grounding.path`) in a single click — no scrolling to a log.
2. **Trust is visible, not asserted.** Every answer shows its evidence: each
   `citation` is inspectable (label + source snippet), and the grounding state
   is shown plainly, including the degraded cases (`issues[]`, `path == "none"`).
3. **Scope is legible.** A scoped persona (support, marketing) can see, at a
   glance, that the view is filtered to their categories and that the filter
   happened *at retrieval, before the model* — never framed as the model
   choosing to hide things.
4. **Role → render is observably different.** Switching persona changes the
   answer *shape* (executive headline+metric, marketing theme+trend, support
   snippet+policy), driven by `audit.intent` and role — demonstrable by
   comparing two personas on comparable questions.
5. **Every state has a design.** Empty, loading, grounded answer, role-scoped
   answer, graceful-degradation, and error (distinguishing `400` from `502`) are
   each a deliberate, documented screen — none is a blank or a default.
6. **Cost/latency honesty is on screen.** The $0-per-query / low-latency
   reality (`cost_usd`, `latency_ms`, `tokens`) is surfaced, because it is a
   true and distinctive property of this build.

(1–3 are the primary bar for D1; 4–6 sharpen it.)

---

## 5. Constraints

- **Design must not outrun governance.** Access scope is enforced server-side at
  retrieval (M6), before the LLM. The UI may *show* scope and *explain* it, but
  must never offer a control, chart, or view that could surface a role data its
  `ACCESS_POLICY` scope forbids. Any analytics / evidence / chart view is fed by
  the **same M6-scoped retrieval** that produced the answer — there is no second,
  unscoped data path for the UI.
- **The audit record is the design's raw material, but it is read-only.** The UI
  renders `audit` fields; it does not compute or infer new facts the backend did
  not return. If a signal is not in the response, it is not shown (and that gap
  becomes a `03_handoff.md` item for the Developer, not a UI fabrication).
- **Provider mode is invisible.** Two provider modes exist (free-tier ↔ Azure
  OpenAI, via the adapter pattern). The UI must behave identically in both;
  mode is not a user-facing concept. The `$0` cost shown is a real consequence of
  free mode, not a design claim.
- **Reference-grade, not production.** Portfolio-quality clarity over feature
  breadth. No auth, no streaming, no multi-tenant concerns — those are out of
  scope for this iteration (per PRD §3 non-goals and the M8 note).

---

*Next (after D1 approval): `01_wireframes.md` — lo-fi annotated layouts for every
state, then `mockups/<surface>.html` for D2.*
