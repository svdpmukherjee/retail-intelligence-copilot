# Spec M4: Retrieval & agents

## User story
As a retail staff member asking a natural-language question, I want the copilot to pick the
right strategy per question — exact SQL analytics for counts/averages/trends/top-N, semantic
retrieval over reviews for themes/reasons, document retrieval for policy/warranty/how-to — and
merge the results into one grounded, cited answer, so that I can trust the numbers (no
hallucinated aggregates) and verify every claim against its source. This runs at $0 in CI on
the free/local path; Azure LLM + any hosted reranker sit behind the provider seam, gated.

## Module acceptance criteria
- [ ] A **router** classifies each question's intent into `sql` / `review_rag` / `docs_rag` /
      `sql+rag` and attaches an **access scope** object; every retrieval flows through a single
      choke point that applies scope as filters (M4 passes scope through — full enforcement is
      M6). Router has an LLM path and a deterministic keyword-rule fallback (works with no LLM).
- [ ] A **SQL agent** does text-to-SQL over M2 Gold `structured` and returns exact aggregates
      with **no numeric hallucination**: generated SQL is validated **read-only** (single
      `SELECT`, no DDL/DML/multi-statement) before execution; unsafe SQL is refused loudly.
- [ ] **review-RAG and docs-RAG** agents run **hybrid search (vector + keyword) → reciprocal-
      rank fusion → rerank**, filtered by `source_type` (`review` vs `doc`) plus the scope
      choke point, and return `SearchHit`s with scores and metadata for citation.
- [ ] A **composer** merges tool outputs into one answer with **inline citations** ([n] → source
      id); uncited claims are blocked/flagged (full citation enforcement is shared with M6, but
      M4 produces cited output). It has an LLM path and an **extractive/deterministic fallback**
      so the free path returns a grounded cited answer with no hosted model.
- [ ] **Query-time only** (PRD §4): embed-query → hybrid search → rerank → generate; no ETL /
      Databricks / bulk embed at query time. Every LLM call is wrapped in `CostLedger`; Azure
      LLM and any hosted reranker raise `GoAheadRequired` unless keys + an explicit go-ahead
      flag are set. Each answer emits an **audit record** (query, role, sources, tool path,
      tokens, cost).
- [ ] A **real, non-mocked** end-to-end smoke (free path, local pgvector, no hosted model) —
      live query → grounded, cited answer — passes; `ruff`/`black` clean on `backend/agents/`
      and new `backend/retrieval/` files.

## Sub-modules (ordered, each build → verify → integrate)

### M4.1 LLM provider adapter + query cost wrapper
- Goal: one `LLM` interface with a real free/local path, a deterministic no-LLM fallback, and a
  gated Azure path — the shared dependency for router, SQL agent, and composer.
- Acceptance criteria:
  - [ ] `get_llm()` returns a `FreeLLM` when `provider_mode=free` and a gated `AzureLLM` when
        `azure`. Both expose `complete(system: str, user: str, *, ledger, max_tokens) -> str`.
  - [ ] `FreeLLM` calls an OpenAI-compatible endpoint when `free_llm_base_url`/`free_llm_model`
        are set (real $0 if local, e.g. Ollama); when **no** LLM is configured it reports
        `available=False` so callers use their deterministic fallback (CI stays green, $0, no
        hosted model). `AzureLLM` raises `GoAheadRequired` unless `azure_llm_go_ahead=true` +
        `azure_openai_endpoint`/`azure_openai_api_key`/`azure_openai_chat_deployment` are set.
  - [ ] Every `complete()` estimates tokens and records them via the passed `CostLedger`
        (free path = $0); a cap breach refuses **before** the paid call (reuse `CostLedger.add`).
- Build steps:
  1. Add Settings keys: `azure_llm_go_ahead` (bool, default `false`), `llm_max_tokens`
     (int, default 512), `azure_llm_usd_per_1m_tokens` (float, est. for the ledger). Document in
     `backend/.env.example` (reuse existing `free_llm_*` and `azure_openai_chat_deployment`).
  2. Write `backend/agents/llm.py`: `LLM` protocol, `FreeLLM` (httpx → OpenAI-compatible
     `/chat/completions`, `available` property), `AzureLLM` (gated, mirrors `AzureEmbedder`),
     `get_llm()` factory keyed off `provider_mode`. Reuse `GoAheadRequired` from
     `retrieval.embeddings`.
- Files to touch: `backend/app/config.py`, `backend/.env.example`, `backend/agents/llm.py`,
  `backend/tests/test_llm.py`.
- Integration point: reuses M1 `Settings`/`provider_mode`, `CostLedger`, and the
  `GoAheadRequired` gate pattern from M3; consumed by M4.4/M4.5/M4.6.

### M4.2 Hybrid retrieval (vector + keyword → RRF → rerank) with scope choke point
- Goal: the query-time retrieval primitive M4's RAG agents share, reading the M3 `chunks` table.
- Acceptance criteria:
  - [ ] `PgVectorStore` gains `keyword_query(query, k, *, filters)` (Postgres full-text:
        `to_tsvector('english', text)` + `plainto_tsquery`, backed by a GIN index added in
        `chunks_ddl`) and `query(...)` gains an optional `filters` arg (`source_type`, and
        `source`/`category` for the M6 scope hook). `AzureSearchStore` stays gated.
  - [ ] `hybrid_search(query, k, *, filters)` embeds the query (`get_embedder`), runs vector +
        keyword retrieval over `hybrid_candidates` each, fuses by **reciprocal-rank fusion**
        (`rrf_k`, default 60), reranks the top `rerank_candidates`, and returns the top-`k`
        `SearchHit`s. Deterministic (stable ordering, tie-broken by id).
  - [ ] Rerank seam: `reranker=none` (default, identity passthrough of fused score, $0),
        `reranker=local` (optional sentence-transformers cross-encoder, $0, lazy-loaded),
        `reranker=azure` (hosted, raises `GoAheadRequired` unless `rerank_go_ahead=true`).
- Build steps:
  1. Add GIN full-text index to `chunks_ddl` in `backend/retrieval/schema.py`; add
     `keyword_query` + `filters` support to `backend/retrieval/vector_store.py` (filters build a
     parameterised `WHERE` — the single access choke point).
  2. Write `backend/retrieval/rerank.py`: `get_reranker()` → identity / local cross-encoder /
     gated azure.
  3. Write `backend/retrieval/hybrid.py`: `hybrid_search(...)`, `rrf_fuse(...)` helper.
  4. Add Settings keys: `reranker` (`none|local|azure`, default `none`), `rerank_go_ahead`
     (bool), `rerank_model_local`, `retrieval_top_k` (default 6), `hybrid_candidates`
     (default 30), `rerank_candidates` (default 20), `rrf_k` (default 60).
- Files to touch: `backend/retrieval/schema.py`, `backend/retrieval/vector_store.py`,
  `backend/retrieval/rerank.py`, `backend/retrieval/hybrid.py`, `backend/app/config.py`,
  `backend/.env.example`, `backend/tests/test_hybrid.py`.
- Integration point: reads the M3 `chunks` table via the existing `VectorStore`/`Embedder`
  seams; `filters` reserves the M6 access-policy choke point; consumed by M4.3.

### M4.3 review-RAG & docs-RAG agents
- Goal: two thin agents over `hybrid_search`, each pinned to its `source_type`.
- Acceptance criteria:
  - [ ] `review_rag(query, scope, k)` calls `hybrid_search` with `source_type="review"`;
        `docs_rag(query, scope, k)` with `source_type="doc"`. Both merge `scope` into `filters`
        (the choke point) and return `list[SearchHit]`.
  - [ ] A query retrieves review chunks vs doc chunks distinctly by `source_type`; returned hits
        carry the metadata the composer needs to cite (`asin`/`category` or `doc_title`/`section`).
  - [ ] **Docs are not product-scoped (D-1).** The `category` key in a role's scope is a product
        filter; doc chunks have no `category`. The shared helper **drops `category` from the merged
        filters when `source_type == "doc"`** (docs stay scoped by `source_type`), and **keeps it
        for `source_type == "review"`**. A category-scoped role (`support`/`marketing`) therefore
        retrieves docs normally while review/SQL category enforcement is unchanged.
- Build steps:
  1. Write `backend/agents/review_rag.py` and `backend/agents/docs_rag.py` (thin wrappers;
     a shared `_rag(source_type, ...)` helper is fine).
  2. In the shared helper, after merging `scope`, drop the `category` filter on the `"doc"`
     path (keep all other scope keys) before calling `hybrid_search`.
- Files to touch: `backend/agents/review_rag.py`, `backend/agents/docs_rag.py`,
  `backend/agents/_rag.py`, `backend/tests/test_rag_agents.py`.
- Integration point: built entirely on M4.2 `hybrid_search`; consumed by the router (M4.5) and
  composer (M4.6).

### M4.4 SQL agent (text-to-SQL over Gold `structured`, read-only)
- Goal: exact aggregates over M2 Gold `structured` with a hard read-only guard.
- Acceptance criteria:
  - [ ] `sql_agent(query, scope, ledger)` loads Gold `structured` (Delta → pyarrow, registered
        in an in-memory **DuckDB**), generates SQL via `get_llm()` (schema + columns in the
        prompt), and returns `{sql, rows, columns}`. Column set is the M2 `STRUCTURED_COLUMNS`.
  - [ ] A **read-only validator** accepts only a single `SELECT` (no `;`-chained statements, no
        `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/ATTACH/COPY/PRAGMA`) that **has a `FROM`**;
        anything else raises a typed error — no unsafe SQL ever executes. Results are exact (no
        LLM-invented numbers).
  - [ ] **The agent never leaks a DuckDB error (D-3).** When generated SQL fails validation *or*
        raises at execution, the agent **regenerates once** and retries; if the retry still fails
        it raises a typed `SQLComputeError`, which `pipeline.answer` catches by dropping the SQL
        source (recorded in `tool_path`/audit) so the composer returns a clean
        *"couldn't compute"*-style 200 answer — never a raw `BinderException`/502.
  - [ ] When no LLM is available, the agent refuses the generation step with a clear message
        (deterministic tests exercise the guard + execution with hand-written SQL).
- Build steps:
  1. Write `backend/agents/sql_agent.py`: load Gold `structured` (reuse the Delta-read pattern
     from `retrieval/index_reviews.py`), `_safe_select(sql)` validator (single read-only `SELECT`
     **with a `FROM`**), DuckDB execute, LLM text-to-SQL prompt. Wrap the LLM call in the passed
     `CostLedger`.
  2. `sql_agent` runs generate → validate+execute and, on `UnsafeSQLError` or any DuckDB execution
     error, regenerates **once**; a second failure raises typed `SQLComputeError`. `pipeline.answer`
     catches it, sets `sql_result = None`, records the failure in `tool_path`/audit, and lets the
     composer answer gracefully (D-3 — no binder leak, no 502).
  3. Add `duckdb` to backend deps.
- Files to touch: `backend/agents/sql_agent.py`, `backend/agents/pipeline.py`,
  `backend/pyproject.toml`, `backend/tests/test_sql_agent.py`.
- Integration point: reads M2 Gold `structured` (the M2→M4 boundary); uses M4.1 `get_llm`;
  consumed by the router and composer.

### M4.5 Router (intent + scope passthrough, dispatch)
- Goal: classify intent + scope and dispatch to the right tool(s).
- Acceptance criteria:
  - [ ] `route(query, role) -> RouteDecision{intent, scope, rationale}` where intent ∈
        `{sql, review_rag, docs_rag, sql_rag}`. **Routing is rule-first (D-2):** high-confidence
        keyword patterns (why-changed → `sql_rag`; counts/average/total/trend/top-N/how many/
        per-month → `sql`; policy/warranty/return/how-to/manual → `docs_rag`) win *deterministically*
        and the LLM is **not** consulted. The LLM classifier is consulted **only** when no pattern
        matches (the would-be `review_rag` default); a valid JSON intent then wins, otherwise the
        route stays `review_rag`. With no LLM available the same rules run and default to `review_rag`.
  - [ ] `scope` is a structured object derived from `role` (default: all sources/categories) and
        is passed unchanged into retrieval filters — the single place M6 will tighten.
- Build steps:
  1. Write `backend/agents/router.py`: `RouteDecision` model, `route(...)` with rule-first
     precedence (rule hit wins deterministically; LLM consulted only on no-match), the keyword
     rules, JSON-intent LLM classification for the ambiguous case, and `derive_scope(role)` stub
     returning the open scope + a docstring noting M6 will enforce it.
- Files to touch: `backend/agents/router.py`, `backend/tests/test_router.py`.
- Integration point: uses M4.1 `get_llm`; produces the dispatch + scope consumed by M4.6.

### M4.6 Composer + end-to-end pipeline + `/query` API
- Goal: merge tool outputs into one grounded, cited answer and wire the whole pipeline behind an
  API route with an audit record.
- Acceptance criteria:
  - [ ] `compose(query, sql_result, hits, ledger) -> AnswerResult{answer, citations, audit}`
        produces an answer with **inline [n] citations** mapping to source ids (chunk id or
        `sql`); claims without a backing source are blocked/flagged. LLM path when available;
        **extractive/deterministic fallback** otherwise (assembles grounded sentences from top
        hits + SQL rows, trivially cited) so the free path never needs a hosted model.
  - [ ] `answer(query, role) -> AnswerResult` wires router → (sql_agent and/or review/docs_rag)
        → composer, all under one `CostLedger`, and emits an `audit` dict (query, role, intent,
        sources, tool_path, tokens, cost). `POST /query {query, role}` returns it; upstream
        failures become a typed `HTTPException` with JSON `detail` (never an unhandled 500).
  - [ ] Every citation in the answer resolves to a source actually returned by a tool
        (no dangling/uncited references).
- Build steps:
  1. Write `backend/agents/composer.py` (`AnswerResult` model, LLM + extractive paths,
     citation-resolution check).
  2. Write `backend/agents/pipeline.py` (`answer(...)` orchestration + audit record).
  3. Add `POST /query` to `backend/app/main.py` (async route, try/catch → `HTTPException`).
- Files to touch: `backend/agents/composer.py`, `backend/agents/pipeline.py`,
  `backend/app/main.py`, `backend/tests/test_composer.py`, `backend/tests/test_pipeline.py`.
- Integration point: consumes M4.3/M4.4/M4.5; exposes M4 through the FastAPI app (full UI is M8).

## Test plan
- M4.1: unit — `get_llm()` returns `FreeLLM` in `free` mode with `available=False` when no
  `free_llm_*` set; `AzureLLM.complete` raises `GoAheadRequired` without go-ahead; ledger records
  on `complete` and a cap breach refuses before the call.
- M4.2: unit — against local pgvector (seed a few review + doc chunks): `keyword_query` returns
  a keyword match; `hybrid_search` fuses vector+keyword via RRF and respects `source_type`/scope
  filters; `reranker=none` preserves fused order; `reranker=azure` raises gated. If pgvector is
  unavailable, the Tester reports plainly (not PASS), per `testing.md`.
- M4.3: unit — `review_rag` returns only `source_type="review"` hits, `docs_rag` only `"doc"`.
- M4.4: unit — `_safe_select` accepts a `SELECT`, rejects `DROP`/multi-statement/DML; a
  hand-written aggregate over the committed Gold sample returns exact rows via DuckDB; generation
  step refuses cleanly when no LLM.
- M4.5: unit — rule-based router maps representative questions to the four intents; `scope` is
  attached and passes through to filters.
- M4.6: unit — extractive composer yields inline [n] citations all resolving to returned sources;
  an uncited claim is flagged/blocked; `POST /query` returns an `AnswerResult` with an audit dict.
- Module end-to-end smoke (the one real check): `provider_mode=free`, local pgvector, **no hosted
  model** — index the tiny committed slice (M3 CLIs), then `answer("what are common complaints
  about <seeded product/category>?", role="support")` returns a grounded answer whose citations
  resolve to retrieved review chunks, at $0, non-mocked. (If a local LLM endpoint is configured it
  exercises the LLM path; otherwise the deterministic path still yields a grounded cited answer.)

## Security & cost notes
- **Expected cloud spend for M4 = $0; cap = $0 in CI.** Default path is free/local LLM (or the
  deterministic fallback) + local embedder + local pgvector + `reranker=none` — no cloud call.
- **Gated paths (CHECKPOINT 1 is also the cost go-ahead):** `AzureLLM` (gpt-4o-mini-class chat)
  and `reranker=azure` run only with keys + `azure_llm_go_ahead`/`rerank_go_ahead=true`. Each
  query's LLM/rerank spend is bounded by `CostLedger` (`max_cost_usd`, default $1/query) and
  logged in `COST.md`; realistic Azure cost is a few cents per query. CHECKPOINT 1 authorizes
  only committing the $0 pipeline — **not** any Azure LLM or hosted-rerank call.
- **Access control:** scope is derived from `role` and applied as retrieval filters at the single
  choke point in `hybrid_search`/the store `WHERE` clause (before the LLM) — M4 wires the hook
  open; M6 tightens it. SQL safety is enforced by the read-only validator, not by prompting.
- **Secrets:** Azure OpenAI / `free_llm_*` / `database_url` only via `.env` (M1 keys reused);
  never logged. **PII:** Gold/reviews already redacted (M2); docs carry none. **Grounding:**
  composer blocks/flags uncited claims. **Audit:** every answer logs query, role, sources, tool
  path, tokens, cost (feeds M6 audit log + M7 eval).

## Out of scope
- Any Azure OpenAI chat call or hosted reranker run (gated, go-ahead only).
- **Full access-control enforcement, PII refusal rules, and the complete citation-enforcement/
  audit-log store — M6.** M4 only wires the scope choke point open and produces cited output + a
  basic audit dict.
- **Conversation threads / short- & long-term memory / multi-turn context — M5.** M4 answers a
  single question per call.
- **Evaluation gate (recall@k, MRR, faithfulness, cost/latency thresholds) — M7.**
- **React UI and Azure deployment — M8.** M4 exposes only the `POST /query` API route.
