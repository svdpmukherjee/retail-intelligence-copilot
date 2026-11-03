# Answer quality remediation — change proposal

Date: 2026-11-03. Status: **Stages 1–2 accepted; Stage 3 isolated work ready for review; targeted Stage 4 workaround implemented; Stage 5 pending**.

Problem: the copilot can select inappropriate evidence, confuse conversation topics,
present unsupported conclusions as cited facts, and render misleading charts/raw
Markdown. This proposal defines scoped changes to existing modules, not a new module.
Initial findings came from source inspection. Stage 1 subsequently replayed six core questions for both roles, with the specified conversation sequences; the local live review is `/private/tmp/ric-quality-stage1-review.md`.

## Options and decision

| Option | Effort / risk | Cost | Trade-off |
|---|---|---|---|
| A. Formatting and prompt patch | Small / low implementation risk | Local checks $0 | Fixes visible symptoms; leaves evidence correctness unresolved. |
| **B. Measured staged remediation — recommended** | Moderate / bounded per change | Local work $0; paid calls and reindexing separately gated | Establish baseline, correct interpretation/evidence, then synthesis/presentation. Preserve existing adapters and permissions. |
| C. Replace orchestration with an autonomous-agent framework | Large / high | Requires separate estimate | Broad migration; does not automatically solve missing metadata or weak evaluation. |

Selected by the user: **B**. Stage 1 was accepted, and the user subsequently instructed proceeding with Stage 2. The decision is recorded
in `context/DECISIONS.md`; the approved stage-1 scope is localized in the M7 spec.
Later stages require their own scoped review. Do not mark modules DONE from this
direction approval.

## Inventory

H = correctness/trust priority; M = subsequent quality/performance work. Defaults
must be checked against active configuration without exposing secrets. A code gap
does not prove it caused a particular historical answer.

| ID | Priority | Finding / source | Proposed solution | Stage |
|---|---|---|---|---|
| Q01 | H | `memory/manager.py`: all initial “why” questions inherit prior user text. | Resolve missing references; preserve complete standalone questions/topic switches. | 2 |
| Q02 | H | `agents/router.py`: “lowest-rated” selects SQL; combined intent has narrow change-word triggers. | Identify operations/evidence needs; support selection plus explanation instead of keyword precedence. | 2 |
| Q03 | H | `agents/pipeline.py`: review retrieval ignores products selected by SQL; vector filters omit ASIN. | Pass selected product IDs into permission-constrained retrieval; report missing product evidence. | 2–3 |
| Q04 | H | `agents/_rag.py`: permission scope is applied but requested category/period is not extracted. | Normalize entities and intersect requested constraints with access scope. | 2–3 |
| Q05 | H | `sql_agent.py`: column-only prompt lacks types, grain, allowed category values and metric semantics. | Bounded semantic schema; distinguish review averages from product metadata averages; define minimum review count. | 2 |
| Q06 | H | `composer.py`: empty SQL becomes citable “no rows.” | Typed success/empty/failure outcomes; no empty table or emptiness treated as factual evidence. | 2 |
| Q07 | H | `review_rag.py`, `hybrid.py`: top-k examples support unmeasured “most/common” claims. | Separate qualitative synthesis from counted prevalence; define population/denominator and deduplicate reviews. | 3–4 |
| Q08 | H | `grounding.py`: citation syntax/density, not factual support. | Numeric claim validation against SQL; qualitative support assessment against actual passages; honest abstention. | 4 |
| Q09 | H | `gold.py`, `schema.py`: review index lacks rating, exact date and product title. | Preserve metadata/provenance through Gold/chunks/index; explicit versioned schema migration. | 3 |
| Q10 | H | `hybrid.py`: no evidence-sufficiency rejection. | Calibrate with answerable/unanswerable cases; RRF scores are not confidence probabilities. | 3 |
| Q11 | H | Indexers upsert without reconciling deleted/superseded chunks. | Source/version manifests and atomic reconciliation with rollback. | 3 |
| Q12 | H | Embedding model identity is not checked against corpus vectors. | Persist model/revision/dimensions and corpus version; reject incompatible query embeddings even when dimensions match. | 3 |
| Q13 | H | `chunking.py`: whole reviews have no token bound. | Token-aware long-review chunks, stable parent identity/offsets; no count inflation from multiple chunks. | 3 |
| Q14 | H | `gold.py`: SQL/review samples have different caps and newest-first selection. | Measure date coverage and product overlap; disclose dataset limitations; avoid population claims from a biased subset. | 1, 3–4 |
| Q15 | H | `llm.py`: finish reason discarded; default response budget 512 tokens. | Typed generation outcomes, task budgets, bounded recovery for incomplete/empty output. | 4 |
| Q16 | M | `vector_store.py`: whole-question `plainto_tsquery` can overconstrain lexical search. | Focused lexical queries with entities/aliases; measure lexical contribution separately. | 3 |
| Q17 | M | SQL retry lacks previous SQL/error; execution success is not semantic correctness. | Bounded repair with sanitized feedback; verify expected result semantics. | 2 |
| Q18 | M | SQL fetch caps at 200; reported total counts fetched rows only. | Explicit `has_more`; distinguish displayed/fetched rows and exact totals. | 2, 4 |
| Q19 | M | Embedder/reranker factories create short-lived model instances. | Process-level lifecycle and safe reuse; benchmark cold/warm latency and concurrency. | 5 |
| Q20 | H | `ClaimLine.tsx`, `answer.ts`: Markdown rendered as plain text. | Safe Markdown document rendering with citation components and replay parity; no raw HTML execution. | 4 |
| Q21 | H | Marketing charts invent time trends from categories; executive ranks use incoming row order. | Validated chart metadata: category, temporal, or sorted ranking semantics independent of role. | 4 |
| Q22 | M | Evidence previews show first 240 characters; review labels indistinguishable. | Relevant expandable redacted passages and numbered product/date labels where available. | 4 |
| Q23 | H | `eval/answer_eval.py`: docs-pinned path and syntax/keyword proxy; LLM judge lacks evidence bodies. Study SQL checks execution only. | Full-path role/multi-turn evaluation; separate support, semantic SQL accuracy, retrieval, abstention and presentation scores. Reassess model policy afterward. | 1, 5 |
| Q24 | H | Composer mixes untrusted evidence/memory without strong instruction/data boundary. | Delimit untrusted content; prohibit embedded instructions; adversarial evidence tests and server-side scope invariants. | 4 |
| Q25 | H | Live A01/A05: grouped markers `[1, 3]` bypass single-number citation parsing; referenced evidence is dropped and links disappear. | Shared grouped/adjacent citation grammar across validation, source retention, rendering and history; regression cases. | 4 |
| Q26 | H | Live A05: a review update says an issue was fixed, but the answer repeats the old complaint as current. | Respect corrections/updates; distinguish historical/resolved complaints and test contradictory passages. | 3–4 |
| Q27 | M | Live browser: source excerpts display literal `<br />` markup inherited from review text. | Normalize source HTML/entities into safe plain text with provenance; test rendering without executing raw HTML. Plan index migration separately. | 3–4 |

## Ordered delivery

Each stage is its own scoped change/PR. Do not concurrently modify shared pipeline,
memory, composer or index contracts. Use existing `docs/testing/acceptance/` cases
and runners where safe; avoid a duplicate evaluation system. Existing B-15 overlaps
Q01/Q02, B-9 overlaps embedding comparison; reconcile their status during approved
spec work rather than claiming old backlog entries are current.

1. **M7 baseline and regression contract — first implementation scope.** Extend
   `.claude/specs/M7_evaluation.md`, `backend/eval/`, relevant tests, and acceptance
   docs with bounded full-path cases below. Retain docs-only metrics separately.
   Capture real failures, not lower thresholds to obtain green. Success: each core
   case has exact fixture expectations, actual results and PASS/FAIL/NOT RUN.
2. **M4/M5 interpretation and tool execution; M6 invariants.** Q01–Q06/Q17/Q18.
   File domains: `backend/agents/`, `backend/memory/manager.py`, retrieval filters.
   Product-explanation acceptance remains open until stage 3 supplies required
   metadata/coverage; correcting intent alone is insufficient.
3. **M2/M3/M4 evidence foundations.** Q03/Q04/Q07/Q09–Q14/Q16. Plan schema,
   backfill, source reconciliation and rollback first; prove with a small isolated
   index. Full ETL/reindexing is a separately authorized operation.
4. **M4/M6/M8 synthesis and presentation.** Q07/Q08/Q15/Q18/Q20–Q22/Q24–Q26.
   Direct takeaway, few supported findings, optional meaningful chart/table and
   accessible evidence. Validate facts before polishing prose. Do not claim a
   general semantic-support guarantee from citation/numeric checks alone.
5. **M7/M4 integrated validation and tuning.** Q19/Q23. Repeat frozen role,
   multi-turn and browser cases; compare models/rerankers only after measuring
   correctness. Record latency/cost and quality without weakening permissions.

## Acceptance matrix

Use a small synthetic fixture with known products/categories/dates/ratings/reviews
for exact expectations. Separately validate against live data read-only; do not
invent fixed live-data numbers. Fresh = no prior thread. Sequence = same thread
with the exact preceding turns. Run core cases for marketing and executive.

| Case | Query / setup | Required behavior |
|---|---|---|
| A01 | Fresh: What do customers praise most about our Beauty products? | Only permitted Beauty evidence; no prevalence claim without measured counts; label examples honestly. |
| A02 | Fresh: What's the average customer rating by category? | Fixture AVG(rating), review-weighted; marketing sees its three allowed categories, executive all fixture categories. Values match independent expected SQL. |
| A03 | A02 → Why are customers unhappy with our lowest-rated toys? | Standalone Toys request; select eligible lowest-rated products and retrieve their negative evidence; no repeated unrelated averages. |
| A04 | Fresh: Why are our lowest-rated electronics disappointing customers? | Explicit product/minimum-count definition and related reviews; SQL alone cannot explain reasons. |
| A05 | Fresh: What do customers complain about most in their reviews? | Negative evidence; counted themes for prevalence, otherwise explicitly bounded qualitative examples. Praise is not a complaint. |
| A06 | Fresh: What does our return policy say about damaged items? | Distinguish arrival defects, customer-caused damage and shipping-fee refunds; each claim supported by its actual passage. |
| A07 | Product ranking → Why is that? | Resolve genuine antecedent/product set, retain scope; contrast complete topic switch A03. |
| A08 | Unordered category averages for both roles | Category comparison only; no time/sentiment trend or unsorted rank numbers. |
| A09 | Known time series with shuffled dates | Time chart only with temporal dimension, chronological ordering, correct units and SQL-backed points. |
| A10 | Empty selection / no indexed reviews / SQL failure | Three distinct honest outcomes; no empty table, “no rows [1]” evidence, or unrelated replacement products. |
| A11 | Unauthorized category, including follow-up | No unauthorized rows/chunks/memory/citations/chart values; never broaden permissions. |
| A12 | Unknown category or unavailable sales/revenue measure | Explain missing capability and alternatives; no invented columns/values or repeated clarification loop. |
| A13 | Markdown headings/emphasis/lists/table/[n]/[1, 3]; reopen history | Semantic formatting and working evidence; no raw markers, HTML execution or replay discrepancy. |
| A14 | SQL source 4.50, draft says above 4.5 | Correct/reject strict-comparison error; 4.51 is a contrasting valid fixture. |
| A15 | Supporting passage beyond first 240 characters | Actual redacted supporting passage is inspectable; same-category sources distinguishable. |
| A16 | Review says ignore instructions; memory has old unsupported claim | Ignore embedded instructions; do not cite memory as fresh evidence; preserve scope. |
| A17 | Edit review; shorten/delete policy in isolated index | Superseded/deleted evidence absent after reconciliation; rollback restores consistent prior version. |
| A18 | Different embedding model with same dimensions | Detect incompatibility before retrieval. |
| A19 | Long review with complaint near end | Retrieve complaint with token-aware chunks; do not count one review multiple times. |
| A20 | SQL results exceed 200 and display limit | Explicit truncation/returned/displayed semantics; no false exact total. |
| A21 | Provider length-limited, empty or malformed output | Record failure/incompleteness; bounded recovery or honest fallback; no silent partial answer. |
| A22 | SQL fails first attempt | Sanitized error/SQL supplied to repair; read-only/scope guards hold; repaired result matches semantic gold. |

## Validation and operational boundaries

- Exact fixture gold/results are stage-1 work, not completed by this proposal.
  Source findings are confirmed code gaps; live causal hypotheses remain unproven.
- Use bounded fixtures and isolated test DB/index. Verify `_test` redirection before
  pytest; inspect eval helpers that index data. Never rebuild/drop serving data for
  testing. Mocks do not demonstrate live generation quality.
- Missing DB/model/browser/quota means NOT RUN with a reason, never PASS. Do not
  run an expensive baseline merely because a provider key is configured.
- Keep resolved query, tool decisions, selected IDs, SQL, evidence version and
  generation outcome in the operator plane, scrubbed of PII/secrets. Keep operational
  details out of the nontechnical chat answer.
- For bounded gold fixtures require zero scope leaks, dangling citations, numeric
  contradictions and fabricated chart semantics. Qualitative support requires an
  explicit rubric and actual passages; set broader thresholds after the baseline.
- Local planning/checks: $0 hosted spend. This proposal authorizes no paid calls,
  cloud provisioning, full embedding run, corpus replacement or model downloads.
- Decision checkpoint passed: user selected **B, starting with stage 1**. ADR and
  localized M7 scope are recorded. Next: review stage-1 implementation and baseline
  in `docs/modules/M7_answer_quality_baseline.md`; Stage 2 is ready for review in `docs/modules/M4_answer_quality_stage2.md`; stages 3–5 have not started.

## Stage 3 approved localization

User “go ahead” accepts the bounded Stage 2 implementation and approves Stage 3
code/isolated verification in `.claude/specs/M3_answer_quality_stage3_proposal.md`.
Real backfill, serving cutover, paid work and stages 4–5 remain separately gated.
Measured overlap and implementation evidence are in
`docs/modules/M3_answer_quality_stage3.md`; no full answer-quality pass is implied.

## User-authorized practical workaround

The user subsequently explicitly authorized fixing coverage/metadata/output issues.
`.claude/specs/M4_answer_quality_stage4_workaround.md` localizes the approved change;
`docs/modules/M4_answer_quality_workaround.md` records implementation and evidence.
Read-only Silver retrieval for checked SQL-selected products avoids any corpus
backfill. SQL-only summaries are calculated, and citation/format/chart repairs are
implemented. Full Stage3/4 acceptance and general hosted semantic support are not
inferred from this targeted workaround; Stage5 remains unstarted.
