# DECISIONS.md

Durable design decisions (newest at the bottom). Decision → why.

- **Use case = retail customer-intelligence copilot** (reviews/product data), not
  a fraud/finance or logistics corpus. Why: easiest to explain, the canonical
  industry RAG deployment, and it hits both target job ads' skills.
- **Knowledge base = Amazon Reviews 2023 (2019–2023)** + authored policy/manual
  docs + a few real manual PDFs. Why: one coherent source (joins on product/user/
  time); authored docs give trustworthy evaluation ground-truth.
- **Broad SQL, narrow embed.** _(SUPERSEDED 2026-10-27 — see "Broad on both layers,
  capped embed" below.)_ Structured/SQL layer covers ~5–8 categories; the
  embedded RAG layer covers ~2 categories (~1–3M reviews). Why: embedding is the
  cost driver; naive full-corpus embed ≈ $400 vs. curated ≈ $6.
- **Azure stack** (OpenAI, AI Search + pgvector, Blob, Container Apps, Static Web
  Apps) with a **provider-adapter** for a free-tier fallback. Why: both job ads
  require Azure; adapter keeps the demo runnable at ~$0 after the free credit.
- **Databricks = batch/build-time only**, tiny auto-terminating cluster during the
  free-credit month, then OFF. Why: EY values Spark/Databricks; it is never needed
  at query time, so switching it off does not break the demo.
- **RAG ≠ forecasting.** No train/test holdout; all data is the knowledge base.
  Forecasting is explicitly out of scope (off-spec for these roles).
- **PRD.md replaces a multi-doc `project_overview/`.** Why: single public backbone,
  avoids intent drift.
- **Two-level build: module → sub-modules.** Every module is decomposed by the
  planner into ordered sub-modules (`<ID>.n`), each built → verified → integrated
  before the next (~2–6 per module, coherent-block grain). Why: industry-style
  incremental integration; big modules (e.g. M4) are not built in one shot.
  Guardrail: grain is a focused sitting, not per-line, to avoid sub-agent
  cold-start overhead. Human checkpoint stays at the module boundary.
- **Tester kept but tightly scoped.** It verifies only the current scope's
  acceptance criteria + one real smoke; no invented/gold-plated tests; time-boxed.
  Why: testing/CI is an explicit job-ad skill worth showing, but StudyPal's tester
  over-tested. Heavy evaluation (relevance/faithfulness/cost/latency) lives only in
  M6, not in every module's tester.
- **M1: provider-adapter is a config seam only.** M1 ships `PROVIDER_MODE`
  (`azure|free`) on `Settings` but no adapter implementations; the real Azure↔free
  clients arrive with the layers that need them (M3/M4/M7). Why: avoid speculative
  code before there's a caller.
- **M1: CostLedger rejects the breaching entry (not record-then-raise).** Both USD
  and token ceilings are read from `Settings` (defaults $1.0 / 8000 tokens, env-
  overridable) and checked before recording, so running totals can never exceed a
  cap. Why: a ceiling that can be crossed isn't a ceiling.
- **M1: IaC is inert stubs; cost gate holds at $0.** `infra/main.bicep` declares no
  resources (module refs commented); `budget.bicep` carries the consumption budget +
  alert for when real provisioning starts later. Bicep param naming (`namePrefix`,
  `location`) anticipates future `AZURE_NAME_PREFIX`/`AZURE_LOCATION` settings — add
  those to `Settings` in the first deploying module.
- **Added a Conversation & Memory module (new M5); renumbered the rest.** New M5 =
  threads + short-term history + long-term user preferences + a memory manager
  (governed by the same PII/access rules as retrieval). Renumber: Governance M5→M6,
  Evaluation M6→M7, Serving & UI M7→M8, Documentation M8→M9. Why: the copilot is a
  multi-turn chat where users iterate against the KB; memory is core, not optional,
  and showcases modular expansion. NOTE: earlier references (M1 doc / decisions) that
  say "serving = M7" now mean **M8**; "adapters in M3/M4/M7" now mean M3/M4/**M8**.
- **Knowledge graph = optional stretch.** Documented in PRD §3 as an extension of the
  memory layer (product↔issue↔fix, user↔preference; multi-hop recall), built only if
  time allows. Why: shows awareness of graph RAG without the build/cost of a core
  graph store; the vector KB + SQL already cover the committed use cases.
- **M2: ETL runs locally by default; Databricks/Blob gated behind a seam.** The
  medallion pipeline is PySpark + Delta in Spark **local mode** over a tiny committed
  synthetic sample, so it builds, tests, and runs in CI at $0. `ETL_RUNTIME`
  (`local|databricks`) and `ETL_STORAGE` (`local|blob`) mirror M1's `PROVIDER_MODE`;
  the Databricks/Blob branches exist but raise a "requires human go-ahead" error until
  explicitly enabled. Why: same cost gate as M1 — nothing provisions to verify; the
  real-volume run is a deliberate, logged step.
- **M2: PII redacted at ingestion in Silver, single enforcement point.** `redact_pii()`
  (in `silver.py`) SHA-256-hashes `user_id` with a `Settings` salt (`PII_HASH_SALT`,
  SecretStr) → `user_id_hash`, drops raw `user_id` + reviewer `name`, and regex-scrubs
  email/phone from `title`/`text`. It **raises if the salt is unset**, so Silver is
  never written unsalted; no raw reviewer PII reaches Silver/Gold. Scope caveat:
  scrubbing covers `title`/`text` only (per spec) — `description`/other free text is
  **deferred to M6 governance**. Why: security rule mandates redaction at ingestion;
  one choke point keeps it auditable.
- **M2: Gold splits broad-SQL from narrow-RAG tables** (`gold/structured` ⊆
  `sql_categories`, structured cols + join keys, no free text; `gold/reviews` ⊆
  `rag_categories`, text/metadata only, no PII cols) + a `_manifest.json` (per-layer
  counts, window, categories, run timestamp). This is the M3/M4 read boundary. Why:
  enacts the "broad SQL, narrow embed" decision at the data layer.
- **M2: build-env note.** The pipeline needs a JDK (installed `openjdk@17`; keg-only,
  set `JAVA_HOME`) and a Python 3.12 venv (system Python is 3.9). Tests that build
  DataFrames from Python rows must set `PYSPARK_PYTHON` (driver 3.12 vs worker 3.9).
  CI must provision both. Why: recorded so later ETL/CI work doesn't rediscover it.
- **Broad on both layers, capped embed (2026-10-27, supersedes "Broad SQL, narrow
  embed").** Both Gold layers now cover **15 categories**. SQL is capped at **100k
  reviews/category**; RAG at **15k reviews/category** (~225k reviews max). Why: the
  data strategy changed to broad-on-both — wider category coverage is more
  demonstrably useful, and with `text-embedding-3-small` (optionally 512-dim) the
  embedding bill is only a few dollars one-time and the vector bulk is ~1.4 GB
  (~0.5 GB at 512-dim), so per-category caps — not category count — are the right
  cost lever. Quality plateaus well before 15k/category; retrieval reliability is
  earned by M4 hybrid-search + rerank and the M7 eval gate, not by raw row count.
  **Rejected alternative:** the prior narrow-embed (~2 categories, ~1–3M reviews)
  strategy — it gave deep-but-narrow coverage and leaned on volume for quality;
  dropped because breadth demos better and caps control cost more directly than a
  tiny category set does. Cost/infra impact (all deferred, gated): real embedding +
  any Databricks full-corpus run is logged in `COST.md`; the ~225k-vector bulk lives
  in **pgvector** (Azure AI Search free tier, 50 MB, is now a tiny demo slice only,
  revising PRD §9). PRD §5 and §9 updated to match.
- **M3 decisions (recorded now, implemented when M3 is built).** (1) Embedding model
  = `text-embedding-3-small`, optionally reduced to **512 dims (Matryoshka)** to
  shrink the index. (2) Vector **bulk lives in pgvector**; Azure AI Search free tier
  is a tiny demo/curated slice only. (3) RAG reliability comes from **M4 hybrid
  search + rerank** and the **M7 eval gate**, not from embedding more rows. Why:
  these follow from the broad-on-both/capped-embed change above; pinned here so M3
  starts from a settled position. No embedding is run and no spend occurs until M3
  is explicitly built and approved.
- **M3: one unified `chunks` table is the M3→M4 read boundary.** Reviews and docs
  live in the SAME pgvector table, separated by `source_type` (`review|doc`), not in
  two stores. Columns: `id`, `source_type`, `text`, `embedding vector(dim)`,
  `category`/`asin`/`year` (review metadata), `doc_id`/`doc_title`/`section`/
  `chunk_index` (doc metadata), and a reserved `source` column. `CHUNK_COLUMNS` +
  `SearchHit` are the contract M4 reads; `source_type` drives docs-RAG vs review-RAG
  routing; `source`/`category` are the hooks M6 access-policy filters on at retrieval.
  Why: one schema is simpler to query and keeps the access-policy choke point single.
- **M3: vector dim is set by the active embedder, fixed at table creation.**
  `chunks_ddl(dim)` takes the dimension as an argument; the factory passes
  `get_embedder().dim` (free = 384, Azure = `azure_embedding_dim`, default 512). Not
  hard-coded. Consequence: a table created at one dim rejects vectors of another
  (`expected N dimensions`). This surfaced as a test-isolation bug (M3.2's dim-3 test
  table colliding with real 384-dim runs); fix = test fixtures drop `chunks` on
  setup/teardown. Note for M4/ops: switching embedder dim means rebuilding the table.
- **M3: free/local embedder is the real $0 CI path; Azure embed stays gated.**
  `FreeEmbedder` (sentence-transformers `all-MiniLM-L6-v2`, 384-dim) runs for real at
  $0 and is the non-mocked path exercised in CI. `AzureEmbedder` (text-embedding-3-small,
  optional 512-dim Matryoshka via the `dimensions` param) and `AzureSearchStore` both
  raise `GoAheadRequired` unless keys + an explicit `azure_embedding_go_ahead` flag are
  set — the Developer added that flag (not in the original spec) so the gate needs an
  intentional toggle, not just presence of keys. Bulk embedding is wrapped in
  `CostLedger` with `max_embedding_usd` (default $5) as the cap. Why: reference build
  runs at $0; the real Azure full-corpus embed (~$0.20–$1.00) is a deliberate, logged,
  gated step, consistent with the M1/M2 cost gate.
- **M3: build-env note.** No project Python env existed; M3 used a Python 3.12 venv and
  added backend deps `sentence-transformers`, `pgvector`, `psycopg[binary]`,
  `deltalake[pyarrow]` (Gold is a Delta table — pyarrow alone ignores the Delta log),
  `pypdf`, and an optional `docs-gen` extra (`reportlab`, only for regenerating the
  committed sample PDFs). The real store tests need a local pgvector Postgres
  (`infra/docker-compose.yml`, `pgvector/pgvector:pg16`); they skip-with-reason when it
  is unreachable rather than silently passing. CI must provision 3.12 + these deps +
  a pgvector service. Why: recorded so M4/CI doesn't rediscover it.
- **M4: the $0 free path needs no hosted model — a deterministic layer backs every agent.**
  The router falls back to keyword rules, the composer to an extractive (one-cited-line-per-
  source) answer, when `get_llm().available` is false. `FreeLLM` calls an OpenAI-compatible
  endpoint only if `free_llm_base_url`/`free_llm_model` are set (e.g. local Ollama, still $0);
  `AzureLLM` and `reranker=azure` raise `GoAheadRequired` unless keys + an explicit go-ahead
  flag (`azure_llm_go_ahead`/`rerank_go_ahead`) are set. Consequence: CI stays green and $0
  with no model; SQL text-to-SQL is the one capability that genuinely needs an LLM, so on the
  free path the SQL agent refuses generation cleanly (typed error → `POST /query` 502), it
  does not fabricate. Why: keeps the reference build runnable at $0 while the cloud path is a
  deliberate, logged, gated step, consistent with M1–M3.
- **M4: hybrid search = vector + Postgres full-text (GIN) → reciprocal-rank fusion → rerank.**
  `hybrid_search` embeds the query, pulls `hybrid_candidates` (default 30) from each of the
  vector and keyword arms, fuses by RRF (`rrf_k`=60), reranks the top `rerank_candidates`
  (default 20), returns top-`retrieval_top_k` (default 6). Deterministic — ties broken by id.
  The reranker is a seam: `none` (identity, default, $0), `local` (sentence-transformers
  cross-encoder, lazy-loaded so `none` never imports it), `azure` (gated). Keyword search adds
  no dep — Postgres `to_tsvector`/`plainto_tsquery` backed by a GIN index in `chunks_ddl`. Why:
  PRD §6 calls for hybrid + rerank; reliability comes from this + the M7 eval gate, not row count.
- **M4: `build_where` is the single retrieval access choke point (the M6 hook).** All scope
  filtering goes through one parameterised WHERE builder shared by `query` and `keyword_query`,
  accepting only `source_type`/`source`/`category` (str → `=`, list → `= ANY`) and raising on
  any other column. The router derives an OPEN scope (`{}`) for every role today; M6 tightens
  `derive_scope(role)` and nothing else. `source_type` pinning (review vs doc) always wins over
  a scope key, so an agent can't be tricked across its corpus. Why: one choke point keeps the
  access policy auditable and is the clean seam M6 builds on; filtering before the LLM (not by
  prompting) is the security rule.
- **M4: SQL safety is a hard read-only guard, not a prompt.** `_safe_select` accepts a single
  `SELECT` only (strips one trailing `;`, rejects any other `;`, blocks DDL/DML/ATTACH/COPY/
  PRAGMA/read_*/glob, and CTEs), runs in in-memory DuckDB with `enable_external_access=false`
  over the Delta Gold `structured` table read to pyarrow; the LLM never supplies numbers, so
  aggregates are exact. The guard is conservatively strict (rejects blocked keywords even inside
  string literals) — accepted because Gold `structured` has no free-text column, so the false-
  reject risk is ~nil; if a free-text filter is needed later, strip literals before the scan.
  `run_sql` can surface a raw DuckDB `CatalogException`, so `pipeline.answer` catches generic
  tool exceptions (→ `PipelineError` → typed 502), never an unhandled 500. Why: "exact, no
  hallucinated numbers" (PRD §4) must be enforced in code; safety can't be delegated to the model.
- **M4: grounding is enforced by a citation-resolution check, not by asking the model.**
  `compose` numbers every retrieved source `[n]`; `check_citations` flags dangling `[n]`,
  uncited claim lines, and no-citation answers. An LLM draft that fails is discarded and the
  extractive answer (which cites every line by construction) is used, with the issue logged in
  the audit `grounding` block. Each answer emits an audit dict (query, role, intent, tool_path,
  sources, tokens, cost_usd, latency_ms, grounding) — the feed for the M6 audit log and M7 eval.
  Why: PRD §7 blocks uncited claims; code enforcement is the only trustworthy guarantee.
- **M5: memory is relational + recency/preference, not embedded.** Three plain Postgres tables
  (`threads`, `messages`, `user_memory`) live in the SAME pgvector Docker Postgres as `chunks`
  but are independent of it — no embeddings, no vector recall. Short-term = recent messages on a
  thread; long-term = per-user `finding`/`preference` rows. **Rejected (for now):** semantic/vector
  memory recall and the product↔issue↔fix / user↔preference knowledge graph — kept as the PRD §3
  documented stretch. Why: recency + durable preferences cover the committed multi-turn-refinement
  use case at $0; embedded memory adds a store and cost without a committed use case yet.
- **M5: the memory seam is an additive, default-`None` `context` kwarg — backward compatible.**
  `route(query, role, ledger=None, *, context=None)` and `compose(..., *, context=None)` take an
  optional `MemoryContext`; only when present is `context.render()` prepended to the LLM `user`
  message. With `context=None` the path is byte-for-byte the M4 path (tests assert the exact old
  string). `pipeline.answer(query, role, *, thread_id=None, user_id=None)` is memory-aware only
  when BOTH ids are set and `memory_enabled`; otherwise it is the unchanged M4 single-shot path.
  Why: M5 must not regress M4, and single-shot `POST /query` must keep working.
- **M5: memory never becomes a citable source; grounding rules are untouched.** `context.render()`
  feeds the LLM prompt only — memory is never added to the sources list, so `check_citations` can
  never resolve a `[n]` to a memory item. The extractive/$0 fallback ignores `context` entirely.
  Why: PRD §7 grounding — only retrieved, access-controlled evidence may be cited, not conversation
  memory. Consequence (noted): in pure free mode (no hosted model) the rule-based router and
  extractive composer don't yet *use* loaded history; memory is stored/loaded, but its influence
  shows on the LLM path.
- **M5: persistence is governed at write — summarise → redact → scope-stamp → trim, $0 by default.**
  `MemoryManager.persist` appends the turn's two messages, then writes at most one `finding`
  (only for a non-empty, cited answer — ungrounded answers are never persisted) keyed to the
  turn's `audit` intent/sources, plus any regex-detected durable `preference`. Summarisation goes
  through `get_llm()`/`CostLedger` (capped by `memory_summary_max_tokens`) when a model is available,
  else a **deterministic** first-grounded-sentences summary at $0 (Azure stays gated behind
  `azure_llm_go_ahead`). Content is PII-redacted before write (reused M2 `EMAIL_RE`/`PHONE_RE`,
  copied by value because `data/etl/silver.py` pulls pyspark; no raw `user_id` stored); each row
  carries the turn's retrieval `scope` as JSONB; `memory_max_items` trims oldest per user. Why:
  security rule — redaction + access scope enforced in code at the write point, not by prompting;
  reference build runs at $0.
- **M5: per-user scope + stamped `scope` is the M6 read-enforcement hook; reads filtered by
  `user_id` today.** Memory is keyed by `user_id` and every store read is `WHERE user_id = %s`,
  so no cross-user read is possible; `load` passes `user_id` to `recent_messages` so a non-owner
  gets empty history. Known gaps deferred to M6 (not M5 defects): (a) a caller-supplied `thread_id`
  is NOT verified to belong to `user_id` on the write/persist path (`append_message` lacks the
  owner check `load` has); (b) role→scope enforcement on memory *reads* using the stamped `scope`;
  (c) the reused phone regex is US/NANP-oriented and misses UK/intl formats (PII hardening); (d)
  the durable audit-log store. The memory failure guard degrades any memory error to a plain cited
  answer (error in `audit.memory.error`), never a 500. Why: M5 wires the governance hooks; M6
  tightens `derive_scope` and enforcement, consistent with the single-choke-point plan.
- **M6: role→scope access policy is code, enforced at retrieval before the LLM.** `backend/
  governance/policy.py` holds `ACCESS_POLICY: dict[str, Filters]` and `scope_for_role(role)`:
  `executive`/`admin`/`analyst` → unrestricted `{}`; `support`/`marketing` → `category`-list
  subsets; unknown/empty role → `AccessDenied`. `router.derive_scope` delegates to it, replacing
  M4's OPEN `{}` passthrough; the scope flows through `build_where` (the single choke point) so the
  SQL/retrieval `WHERE` differs per role before any model call; `pipeline.answer` maps `AccessDenied`
  → `PipelineError` → typed 502. **Decisions:** (a) `analyst` kept as full-access because existing
  router/memory tests use it and deny-by-default would break them; (b) scoped roles use `category`
  lists only (not `source`) so retrieval AND the SQL agent — which only honours `category` — stay
  consistent; (c) `source_type` pinning in the RAG agents still wins over a scope key. The category
  subsets are placeholder choices to confirm with the business. Why: PRD §7 — access enforced in
  code at retrieval, not by prompting; one auditable choke point; least privilege (unknown denied).
- **M6: memory is scope-filtered on read and owner-checked on write.** `list_memory` filters
  `user_memory` findings by the role's scope IN THE SQL (JSONB containment on the M5-stamped
  `scope`), not by Python post-filtering, so a finding learned under one scope isn't surfaced to a
  role outside it; a full-access role (`{}`) sees all. A finding stamped `{}` is **hidden** from a
  scoped role (it may have come from an unrestricted query — the safe default). `append_message`
  now carries the same `HAVING EXISTS (threads WHERE id=? AND user_id=?)` ownership check `load`/
  `recent_messages` already had, so a non-owner (or unknown-thread) write raises `PermissionError`
  and persists nothing; `MemoryManager.persist` passes `user_id` through. Preferences are NOT
  scope-filtered (they are the user's own stated preferences, not retrieved evidence). Why: closes
  the two M5-deferred gaps; enforcement in the query, not the model.
- **M6: one hardened PII pattern set + generation-time scrub.** `backend/governance/pii.py` is the
  single source of truth: `EMAIL_PATTERN` (unchanged) and `PHONE_PATTERN` = **5 ordered alternatives**
  (intl `+<cc>`, UK 3-4-4, UK other, US/NANP, local 7-digit), most-specific-first because the first
  match wins; every alternative is `\w`-boundary-guarded. `redact(text)` replaces matches with
  `[EMAIL]`/`[PHONE]`. `data/etl/silver.py` and `backend/memory/manager.py` both import these (local
  regexes removed), and the composer runs `redact(answer)` on BOTH the LLM and extractive paths before
  returning, so a PII string in an LLM draft never reaches the user. Silver redaction is broadened,
  never narrowed (email + US still caught, now UK/intl too). **Over-redaction trade-off (accepted):**
  the legacy US rule still redacts any bare 10-digit run (e.g. a separator-less 10-digit order id),
  and a UK-shaped `0`+10–11-digit run is redacted; years, prices, decimals, short ids, hyphenated
  order ids (`ORD-...`) and citation markers `[n]` all survive. Why: security rule mandates redaction
  at ingestion AND that generated output not leak PII; one choke point keeps it auditable.
- **M6: grounding gate is a first-class control, behaviour-preserving.** `backend/governance/
  grounding.py::enforce_grounding(answer, valid) -> list[str]` is a verbatim extraction of M4's
  `check_citations` (dangling `[n]`, uncited claim lines, no-citation answers); the `_CITE` regex
  moved there and is now exported as `CITE` because the composer reuses it. The composer imports and
  delegates — no semantics/threshold change (all four prior composer tests pass) — and still discards
  a failing LLM draft, serves the grounded extractive answer, and records `["llm draft blocked",
  *issues]` in `audit.grounding`. Why: PRD §7 "uncited claims are blocked" becomes a named, tested,
  independently-targetable governance control (for the Tester and M7), without touching the pipeline.
- **M6: durable audit log is best-effort and never fails the turn; stored query is redacted.**
  `backend/governance/audit.py` adds an `audit_log` table (id, created_at, query, role, intent,
  tool_path/sources/grounding/memory JSONB, tokens, cost_usd, latency_ms) in the same pgvector
  Postgres, with `AuditStore.record`, `get_audit_store`, and an `ensure_audit_schema` one-time guard
  mirroring `ensure_memory_schema`. `pipeline.answer` writes the row after the audit dict is finalised
  via a guarded `asyncio.to_thread(record_audit, ...)` inside try/except — any failure (unreachable DB,
  unset `DATABASE_URL`) is logged as the exception TYPE NAME only (never the URL/secret) and swallowed,
  so the turn always returns; gated on `audit_enabled` (new `Settings` key, default true). **The stored
  `query` is run through `redact()` at the store boundary** (routed back to the developer during the
  build) because `security.md` requires the audit log to store redacted content, and the user query is
  the likeliest free-text PII carrier; the answer text is not persisted so nothing else needs scrubbing.
  Missing optional keys store NULL. **Minor gap (not a defect):** the `audit_enabled=false` path was
  verified by code-read only, not a test. Why: auditability (PRD §7) without ever degrading availability,
  and no raw PII/secrets at rest.
- **M6: build-env note.** The full green suite (138 passed) needs live pgvector
  (`infra/docker-compose.yml`, `DATABASE_URL=postgresql://rag:rag@localhost:5432/rag`) plus
  `sentence-transformers` (free embedder) in the env; the Silver PII ETL tests additionally need
  `pyspark`/`delta-spark` + a JDK (`openjdk@17`, `JAVA_HOME` set) and must run from the repo root
  (`-c data/pyproject.toml --rootdir=.`). Without a DB the DB-backed tests skip-with-reason (not a
  silent pass); without Java the Spark tests error at collection. Dev-DB test rows accumulate in
  `audit_log` and the smoke creates a `chunks` table — periodic `TRUNCATE audit_log; DROP TABLE
  chunks;` clears them (the live pytest fixtures already drop `chunks`). Why: recorded so M7/CI
  provisioning doesn't rediscover it.
- **M7: eval is reuse-only — it measures the system, it cannot change it.** `backend/eval/`
  (metrics, retrieval/answer harnesses, `run_eval`) touches NO pipeline/audit/retrieval/composer/
  memory code. It reads existing seams: `hybrid_search` (pinned `source_type="doc"`), `derive_scope`,
  `docs_rag`, `compose`, `CostLedger`, the pgvector `chunks` index, `index_docs`. Why: an evaluator
  that can alter the thing it measures isn't trustworthy; keeps M7 a thin observation layer.
- **M7: ground truth is a small authored docs-RAG set; retrieval metrics bypass the router.**
  10 committed Q→doc / Q→A items over `data/docs/` (authored policies/manuals give trustworthy
  pairs per `testing.md`); no SQL/LLM-only questions in the $0 set. recall@k/MRR run through
  `hybrid_search` pinned to docs (not the router), so they measure retrieval directly and
  deterministically (both 1.0 on the slice — a smoke-level signal, not a benchmark). Two initial
  fixtures violated this ($0-docs-answerable) rule — one "how many" question routed to the SQL
  agent (needs an LLM), one used `role=support` which the M6 policy blocks from the doc — and were
  corrected (loyalty-benefits policy lookup; role→`analyst`). Why: the eval must measure the
  dimension it claims to, over a corpus with reliable ground-truth, at $0.
- **M7: deterministic $0 judge is the default; Azure LLM-judge gated.** `eval_judge` (new `Settings`
  key, default `"deterministic"`) selects the judge. Default scores `0.5*grounded + 0.5*must_include
  coverage` where `grounded` reuses `governance.grounding.enforce_grounding` + citation presence —
  so CI is free, repeatable, secret-less. `judge_llm` rides `get_llm()`/`CostLedger` and is reached
  only under `eval_judge="llm"` in azure mode with `azure_llm_go_ahead` (else `GoAheadRequired`); the
  $0 path never calls it. Why: the `CLAUDE.md` cost gate forbids silent cloud spend; LLM-as-judge is
  non-deterministic and needs keys — wrong default for a CI gate.
- **M7: the gate must be HERMETIC — the headline correction.** The first build passed only because
  stale `source_type=review` chunks from M2/M4 happened to be in the dev DB. From a clean docs-only
  pgvector (exactly what the CI `eval` job provisions), the free-mode keyword router (no LLM) sent
  ~7/10 gold questions to `review_rag`, which returned nothing → faithfulness 0.65→0.30 → gate
  exits 1. A green local run was hiding a red CI run. **Fix:** the answer harness pins the docs-RAG
  answer path — `answer_docs` = `derive_scope(role)` → `docs_rag` → `compose` under a `CostLedger` —
  instead of `pipeline.answer`, so the measured faithfulness depends ONLY on the authored-docs index
  the harness itself guarantees via `ensure_docs_indexed()`, never on whatever else is in the DB.
  Clean-DB baseline = 0.70; `min_faithfulness` = 0.60 (~0.10 margin). **Deviation from the spec's
  original "runs through `pipeline.answer`" wording** (noted in the module doc). **Trade-offs
  (accepted):** (a) the gate no longer exercises the router — routing quality is uncovered by M7 and
  would need an LLM or a labelled routing set; (b) the harness writes no `audit_log` rows (it bypasses
  `pipeline.answer`); cost/latency come from the harness's own `CostLedger`/timers. **Rejected
  alternatives:** seeding review fixtures so `review_rag` isn't empty (would score grounded-but-wrong-
  source hits ~0.5, a misleading signal), and simply lowering the threshold to mask the problem.
  Why: a CI gate whose result depends on leftover data from other modules is broken; the ground
  truth is a docs set, so the docs-RAG answer path is the meaningful, deterministic thing to measure.
- **M7: config-driven thresholds + CI robustness.** Six thresholds in `backend/eval/thresholds.json`
  (`min_recall_at_k` 0.9, `min_mrr` 0.8, `min_faithfulness` 0.60, `max_cost_per_query_usd` 0.0,
  `max_latency_p50_ms` 5000, `max_latency_p95_ms` 10000), loaded by `run_eval.load_thresholds` —
  tuning the gate is a reviewable one-line data change, no code edit. Quality thresholds sit ~0.10
  below the measured baseline (fails on real regressions, not CI noise); latency caps are generous
  (catch order-of-magnitude regressions, not jitter) and `run_eval` warms up one query before timing
  to exclude model-load. A cold HF model download once hit a 429 and stalled ~175s, tripping the p95
  gate; the CI `eval` job now caches `~/.cache/huggingface`, pre-fetches `all-MiniLM-L6-v2` in a
  separate untimed step, and runs the timed eval with `HF_HUB_OFFLINE=1` set only after the pre-fetch.
  Why: thresholds are policy (data, not code); a network blip must not be scored as a latency
  regression. Open item: the `eval` job's YAML is mirror-of-backend-job but unobserved on a real
  GitHub runner — verify on first push and capture a screenshot under `docs/img/`.
- **D-1 fix (M4): docs are not product-scoped — drop `category` on the docs retrieval path.**
  Category-scoped roles (`support`, `marketing`) carry a product-`category` allowlist in
  `ACCESS_POLICY`; this scope was merged into filters for *both* source types, but doc chunks
  have `category = NULL`, so `category = ANY(...)` matched zero doc rows (AC-9 fail). **Decision:**
  in the single `rag()` merge choke point (`backend/agents/_rag.py`), drop the `category` key when
  `source_type == "doc"`; keep it for `"review"`. Docs stay scoped by `source_type` (and remain
  open to `source`/doc-type scoping if ever needed); reviews/SQL keep category enforcement
  unchanged. **Why:** `_rag.py` is the one place filters are assembled and already knows
  `source_type`, so it is the natural, symmetric home (mirrors the existing source_type-pin
  pattern) with the smallest blast radius; support/marketing should see *all* docs today.
  **Rejected:** (B) stripping `category` inside `docs_rag.py` — splits scope-shaping away from the
  single merge point; (C) modelling doc access as a per-role `source`/doc-type allowlist in
  `ACCESS_POLICY` — changes the scope contract M5/M6 depend on for scope we don't need yet.
- **D-3 fix (M4.4): validate generated SQL is executable, retry once, then degrade — never leak a binder error.**
  `_safe_select` proved the SQL was a single read-only `SELECT`, but not that it was *executable*:
  a semantically-broken query (`SELECT price` with no `FROM`) passed the guard, raised a raw DuckDB
  `BinderException` at execution, and `pipeline.answer`'s catch-all wrapped it into a `PipelineError`
  that `/query` returned verbatim as `502 "Upstream failure: BinderException: ..."`. **Decision
  (Option A, graceful 200):** extend `_safe_select` to also require a `FROM`; in `sql_agent`, run a
  generate → validate+execute attempt and, on `UnsafeSQLError` *or* any DuckDB execution error,
  regenerate **once** and retry; if the retry still fails, raise a typed `SQLComputeError`. The
  pipeline catches `SQLComputeError`, drops the SQL source (`sql_result = None`, records the failure
  in `tool_path`/audit), and the composer answers from whatever remains — or emits a clean
  *"I couldn't compute that from the structured data."* The request returns **200** with an honest,
  uncited answer; the binder text never reaches the user. **Why:** the FROM check is a cheap
  pre-filter but cannot catch the whole BinderException class (unknown column, type mismatch), so the
  execution guard + single retry is what actually closes the leak; a graceful 200 matches the demo/
  AC-2 story better than a 5xx. **Rejected:** (B) a typed error surfaced as a clean 502 — keeps a
  5xx for a case we can answer gracefully; (C) static FROM check only — leaves other
  BinderExceptions leaking as 502.
- **D-2 fix (M4.5): rule-first routing — high-confidence keyword matches win over the LLM; the LLM decides only genuinely ambiguous cases.**
  `route()` called the LLM first and used the keyword rules only when no LLM was available, so a
  nondeterministic local 3B model (`llama3.2:3b`) could override a correct rule match and misroute a
  clear aggregate (AC-2: *"how many reviews per category"* → `review_rag`/`sql_rag`, which then
  "counts the snippets" instead of running a `GROUP BY`). The same input routed correctly by rule
  and incorrectly by LLM on different runs. **Decision (Option A):** invert the precedence. If any of
  the three keyword patterns (why-changed → `sql_rag`; count/average/total/trend/top-N/per-month →
  `sql`; policy/warranty/return/how-to/manual → `docs_rag`) matches, that intent wins deterministically
  and the LLM is **not** called. The LLM is consulted **only** when no rule pattern matches (the
  would-be `review_rag` default); a valid JSON intent then wins, otherwise the route stays `review_rag`.
  Contract (`RouteDecision{intent, scope, rationale}`) is unchanged, so `pipeline.answer` and every
  downstream agent are untouched. **Why:** the regex rules were already correct for exactly the inputs
  the LLM got wrong, so making them authoritative removes the nondeterminism at its source, is the
  simplest thing that satisfies the spec, and as a bonus skips an LLM call (latency/cost) on every
  clear question while still letting the model disambiguate open customer-voice questions. **Rejected:**
  (B) confidence tiers — LLM always runs, rules override only a curated subset: more merge logic and the
  LLM still runs (and can wobble) on clear cases; (C) self-consistency / majority vote over N LLM
  samples: N× cost and latency, still probabilistic, never deterministic for aggregates.
- **M8: unknown role is rejected at the API boundary (400), distinct from governance.**
  `POST /query` validates `req.role` against `ACCESS_POLICY` (already imported for
  `GET /roles`) and raises `HTTPException(400, "Unknown role: ...")` before calling the
  pipeline. An unknown role is a client input error, so 400 — not the 502 the pipeline
  otherwise returns (it wraps `AccessDenied`→`PipelineError`). This is input validation,
  NOT a move of scope enforcement, which stays server-side at retrieval in `build_where`.
  **Why / build-back:** the first M8.1 cut satisfied the spec's 400 criterion only via a
  monkeypatched `answer` raising `AccessDenied` while a real unknown-role request still
  returned 502 — exactly the mocked-pass-while-real-path-differs failure `testing.md`
  warns against. The edge check makes the 400 real and testable with a genuine request.
  **Rejected:** changing `pipeline.py` to let `AccessDenied` propagate — larger blast
  radius into governance for a pure API-layer concern.
- **M8: serving config is env, never hard-coded; CORS origin from Settings.** CORS
  `allow_origins` comes from a new `Settings.cors_allow_origins` (NoDecode + CSV split,
  mirroring `sql_categories`, default `["http://localhost:5173"]`); the frontend backend
  base URL comes from `import.meta.env.VITE_API_BASE_URL` (default `http://localhost:8000`),
  read only in `src/api/client.ts` and baked in at frontend build time. No URL/secret is
  hard-coded in a component, Dockerfile, or CI. Why: code_style/security rules — config via
  environment; one place reads each value.
- **M8: UI is a thin client over the existing contract; server owns thread, client owns
  user.** The React SPA only *selects* a role and renders `AnswerResult` (answer text +
  numbered `[n] label` citations) — it enforces no scope and adds no citable source;
  governance stays server-side. `thread_id` is minted/owned by the backend and echoed
  back for continuity; `user_id` is generated client-side (`crypto.randomUUID()`,
  persisted in `localStorage`) on first use. TS types mirror `composer.AnswerResult` /
  `main.QueryResponse` field-for-field; errors surface a typed `ApiError` (backend `detail`)
  in a visible banner, never a silent blank. Why: keeps the security boundary in one place
  and the UI contract honest against the backend.
- **M8: deployment is packaged but INERT ($0), per the cost gate.** `backend/Dockerfile`
  (python:3.12-slim, non-root `appuser`, CPU-only torch to avoid multi-GB CUDA wheels,
  runs `uvicorn app.main:app`) and `frontend/Dockerfile` (node build → nginx static stage)
  build real images; `infra/webapp.bicep` is a params/vars/outputs-only stub with all
  `resource`/`module` blocks commented (M1 `main.bicep` style), carrying the "needs human
  go-ahead (cost gate)" note; the CI `frontend` job runs `npm ci` + `npm run build` only —
  no deploy, no secrets, no cloud login. Nothing provisions or spends. Real Azure
  provisioning remains out of scope and gated. Why: same cost gate as M1–M7 — packaging is
  safe to commit; a live deploy is a deliberate, logged, approved step.
- **M6 (ADR, 2026-10-28, via `/change`): marketing scope gains `Electronics`.**
  `ACCESS_POLICY["marketing"]` becomes `{Electronics, Beauty_and_Personal_Care, Toys_and_Games}`
  (was `{Beauty_and_Personal_Care, Toys_and_Games, Books}` — `Books` dropped as least
  marketing-relevant). Decision: align the access policy with the PRD §2 marketing persona's
  own flagship question ("complaints about our wireless earbuds… is sentiment improving?") —
  earbuds are `Electronics`, which marketing/product plainly owns the campaigns for. Surfaced by
  the Design-Track value review: the marketing demo could not be answered honestly in-scope and
  the mockup had papered over it by mislabelling an earbud review as `Toys_and_Games`. Why: the
  M6 note already flagged the category subsets as "placeholder choices to confirm with the
  business"; this resolves that placeholder toward the product's stated intent. The PRD §2
  persona questions are unchanged (no product-direction change), so only the M6 spec and
  `policy.py` move, not `PRD.md`. Scopes stay visibly distinct (support keeps
  `Home_and_Kitchen/Automotive/Pet_Supplies`; marketing keeps `Beauty/Toys`; overlap is
  `Electronics` only), so the scope-filtering demo still shows real role-dependent retrieval.
  Rejected alternative: change the marketing *demo question* to one already in scope — rejected
  because it would leave `PRD.md` §2 and the demo diverging, trading a policy mismatch for a PRD
  mismatch. Also carried as design-build conditions (separate specs): PII-redact the proposed
  `citations[].snippet` at the boundary, and keep the mockup's hard-coded category chips out of
  the build until an `audit.scope` field exists.
