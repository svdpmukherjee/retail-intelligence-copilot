# Retail Customer Intelligence Copilot

**Conversational analytics and retrieval-augmented generation over retail reviews,
product metadata and policy documents.**

**The problem.** Retail teams sit on millions of customer reviews and product
records they can't actually query; the insight is trapped, and getting an answer
today means waiting on a data analyst.

**The idea.** Let support, marketing and executives ask about customer reviews,
product ratings, recorded prices and policy documents in plain language. A
capability-aware conversation planner resolves the request, then scoped SQL/review/
document tools supply evidence for the answer. Access filters, calculated summaries,
citations and draft checks reduce known failures; they do not guarantee that every
model claim is correct.

<!-- CHAT GIF: Insert the real recording here, immediately below the product pitch.
     Target: docs/img/chat-interaction.gif. Show a product question, a cited answer,
     opening the evidence panel, then a contextual follow-up. Use the current UI.
     Embed only after the asset exists; see docs/presentation-visuals.md. -->

**Explore:** [How it works](#how-an-answer-is-produced) ·
[RAG engineering](#rag-engineering-decisions) · [Data](#the-data) ·
[Verification](#verification-and-current-boundaries) ·
[How I built it](#how-i-built-it) · [Run locally](#run-locally)

`Python 3.12 · FastAPI · React / TypeScript · PostgreSQL / pgvector · DuckDB · Spark / Delta · Langfuse (optional)`

## What you can ask

| Question | Evidence path |
|---|---|
| “Which five Electronics products have the lowest average rating, with at least 50 reviews?” | SQL over all rated rows for each product; calculated ranking. |
| “What do reviewers dislike about those products?” | Selected product IDs carried forward; bounded Silver review lookup with count/mean verification. |
| “What is the average recorded price in Electronics?” | Product-level SQL, with missing prices disclosed and excluded. |
| “What is the policy for returning a damaged item?” | Retrieval over authored policy documents with inspectable passages. |
| “Show the lowest-rated products and explain the return policy.” | Independent scoped tasks, clarification when needed, then combined evidence and citations. |

These illustrate supported paths, not guaranteed matches. The conversation retains
selection criteria, asks for missing definitions and offers relevant next questions.
The interface provides owner-scoped history and an evidence panel for inspecting
full redacted source passages. Its identity selector is a **demo control**, not
production authentication.

## How an answer is produced

The system combines **structured analytics and unstructured retrieval**. SQL computes
ratings, counts and recorded prices; review and document tools provide textual
evidence. Ingestion is a separate batch operation, never a per-question Spark job.

```mermaid
flowchart TB
    subgraph PREP["Data preparation · batch / build time"]
        RAW["Amazon reviews + product metadata"] --> ETL["Spark / Delta: Bronze → Silver → Gold<br/>Reviewer hashing + email / phone redaction"]
        ETL --> GOLD["Gold structured tables"]
        ETL --> SILVER["Silver source reviews"]
        ETL --> SAMPLE["Sampled review text"]
        DOCS["Authored policies + manuals"] --> CHUNK["Section-aware document chunks"]
        SAMPLE --> EMB["Embeddings + source metadata"]
        CHUNK --> EMB
        EMB --> INDEX["PostgreSQL / pgvector + keyword search"]
    end

    subgraph TURN["Conversation · query time"]
        Q["Question + role + conversation state"] --> PLAN["Capability-aware planner<br/>Clarify criteria or propose typed tasks"]
        PLAN --> ACCESS["Validate tasks + intersect role permissions<br/>Enforce scope at data access"]
        ACCESS --> SQL["SQL tool<br/>Scoped DuckDB calculations"]
        ACCESS --> SEARCH["Review / document tools<br/>Vector + keyword → RRF → optional reranking"]
        SQL --> SELECT["Selected product reviews<br/>Bounded source read + aggregate checks"]
        SQL --> NUM["Calculated numeric summaries"]
        SELECT --> EVIDENCE["Retain retrieved evidence for synthesis"]
        SEARCH --> EVIDENCE
        EVIDENCE --> SYN["Synthesis + citation / draft checks<br/>At most one bounded repair"]
        SYN --> ANSWER["Cited answer or honest source excerpts<br/>Inspectable passages + follow-up suggestions"]
        NUM --> ANSWER
    end

    GOLD --> SQL
    SILVER --> SELECT
    INDEX --> SEARCH

    subgraph OPS["Operator plane · separate from customer chat"]
        AUDIT["Best-effort per-turn audit → admin view<br/>Query, answer, sources, routing, model calls, tokens, cost, latency"]
        TRACE["Optional Langfuse stage traces<br/>Timing, token / cost deltas, redacted input / output"]
    end
    ANSWER -.-> AUDIT
    SQL -.-> TRACE
    SEARCH -.-> TRACE
    SYN -.-> TRACE
```

Access restrictions apply before source evidence reaches synthesis. Shared policy
documents remain separate from category-scoped product/review access. Empty,
denied, partial and unsupported requests have explicit outcomes. Source excerpts
are a visible fallback when a draft fails checks.

Audit records document individual turns; traces help diagnose execution stages.
Both are operator surfaces: cost, tokens, routing and latency stay out of the retail
chat. Langfuse is optional and disabled by default; audit writes are best-effort,
so this is not a guaranteed compliance ledger.

## RAG engineering decisions

| Concern | Implementation and tradeoff | Inspect |
|---|---|---|
| **Planning and tool use** | Dataset capabilities inform typed plans; server validation preserves category, rating, price and selection conditions. Independent questions share a turn budget; greetings, access questions and unsupported measures have explicit paths. | [Planning](backend/agents/query_plan.py) · [Pipeline](backend/agents/pipeline.py) |
| **Hybrid retrieval** | Dense vectors and keyword results are combined with **reciprocal-rank fusion (RRF)**, then bounded to top-k. A local cross-encoder reranker is optional; default is no reranker. The Azure reranker is not implemented. | [Hybrid search](backend/retrieval/hybrid.py) · [Reranking](backend/retrieval/rerank.py) |
| **Chunking and metadata** | Current serving uses one chunk per sampled review and section-aware document chunks carrying source/category/product metadata. Token-bounded overlap, parent IDs, offsets, source hashes and immutable evidence bundles are implemented as an **opt-in, fixture-tested path**, not an activated corpus replacement. | [Chunking](backend/retrieval/chunking.py) · [Evidence foundations](docs/modules/M3_answer_quality_stage3.md) |
| **SQL + source evidence** | SQL uses scoped structured data; supported operations use templates and generated SQL has statement checks. Ratings aggregate all rated review rows per product; prices use product/category grain. Selected-product explanations verify bounded Silver source counts/means against SQL selection. | [SQL tool](backend/agents/sql_agent.py) · [Source-first evidence](docs/modules/M4_answer_quality_workaround.md) |
| **Grounding and citations** | Calculated numeric summaries, grouped citations, inspectable passages and targeted draft guards reduce known numeric, prevalence and policy errors. One bounded repair or source-excerpt fallback limits repeated generation. Citation validity is **not** an entailment proof. | [Citation checks](backend/governance/grounding.py) · [Answer composition](backend/agents/composer.py) |
| **Conversation state** | Owner-scoped threads retain recent context, active selection criteria and pending clarifications. Topic changes replace stale criteria; follow-up suggestions respect supported capabilities and role scope. | [Conversation implementation](docs/modules/M4_conversational_planning.md) · [Memory](backend/memory) |
| **Access and privacy** | Server-owned category permissions constrain SQL and retrieval; unknown roles are denied. Reviewer IDs are hashed at ingestion; email/phone patterns are redacted. Demo role selection does not establish authenticated identity. | [Policy](backend/governance/policy.py) · [PII handling](backend/governance/pii.py) |
| **Auditability and observability** | PostgreSQL audit records and an admin-only read path expose turn evidence and model/tool usage. Optional Langfuse traces expose stage diagnostics, with redacted input/output and restricted metadata. | [Audit storage](backend/governance/audit.py) · [Tracing](backend/observability/tracing.py) · [Admin view](frontend/src/admin) |
| **Evaluation and cost control** | Retrieval recall@k/MRR, answer checks, cost/query and p50/p95 latency have an evaluation harness. Per-query token/cost accounting and explicit hosted-provider opt-ins bound execution. The CI quality evaluation is docs-only, not a full conversational quality certification. | [Evaluation](backend/eval) · [Cost ledger](backend/app/cost.py) · [CI](.github/workflows/ci.yml) |

The provider adapters support a local/free path and optional hosted generation;
Azure integration is a separate configured path. Model choice is task-aware in
OpenRouter mode. A larger configured tier is a policy choice, not evidence of a
new benchmark win. See [model study and its limits](docs/model-comparison.md).

## The data

Built on the real **[Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023)**
corpus from McAuley Lab across **15 product categories**, plus authored policies
and manuals. Recorded local snapshot, documented November 3, 2026:

| Source / serving layer | Recorded scale | Used for |
|---|---:|---|
| Gold structured reviews | **911,308 reviews / 645,448 category-product pairs** | Ratings, counts, product discovery and recorded prices. |
| Sampled review index | **225,000 chunks / 191,007 products** | Semantic and keyword review search. |
| Authored knowledge base | **22 source documents / 79 indexed chunks** | Policy and manual questions. |
| Silver source reviews | Bounded reads for selected products | Evidence where SQL-selected products lack sampled index coverage. |

**Coverage is a design constraint.** The sampled review index contains about
29.59% of SQL category-product pairs; presence does not establish relevance or
exhaustive review coverage. Verified Silver lookup addresses supported
selected-product questions without pretending that ordinary semantic search covers
the full corpus. Review examples do not establish complaint prevalence.

The dataset has **no sales/revenue transactions**. Prices are recorded metadata,
not live quotes, and missing prices remain explicit. The figures above describe a
local operationalized corpus; they are not bundled with a fresh clone.

## Verification and current boundaries

- **Automated checks:** backend tests, lint/format checks and frontend builds are
  configured in CI. The recorded offline backend verification after Gold-test
  isolation was **339 passed / 45 skipped**; DB/provider-dependent checks were
  unavailable. This is a dated local result, not a live CI badge or quality score.
- **Real-system checks:** the repair work recorded **71 browser turns across 27
  distinct questions**, including debugging and rechecks, with **25 named
  latest-outcome checks** and independent Gold aggregates. This is not 71 final
  passes or an exhaustive conversational benchmark.
- **Measured limitations:** some drafts still fall back to excerpts. General
  semantic faithfulness, full-corpus recall, arbitrary generated SQL and all
  natural-language variations are not certified. Later evidence/conversation
  improvements remain subject to quality review; Stage 5 tuning has not started.
- **Serving boundary:** new provenance/token-chunking bundles were fixture-tested;
  no serving backfill or corpus cutover is claimed. Production identity/auth and
  cloud deployment are not established by the local demonstration.

Evidence and methodology: [consolidated quality report](docs/answer-quality-status.md) ·
[frozen acceptance artifacts](docs/testing/acceptance/README.md) ·
[test isolation and verification](docs/testing/unit-testing.md) ·
[recorded verification history](context/WORKLOG.md).

## How I built it

Development uses a human-led orchestrator, specialist AI roles, file-based handoffs
and explicit approval gates. The cards summarize the development method and its
implementation milestones; the product's live data flow is shown above.

<table>
  <tr>
    <td width="50%" valign="top">
      <a href="docs/img/agentic_architecture.svg"><img src="docs/img/build-operating-model.svg" alt="1 · How I run the build: human owner, orchestrator, specialist roles and session memory" width="100%"></a>
      <p><a href="CLAUDE.md">Orchestration rules</a> · <a href="docs/img/agentic_architecture.svg">Detailed operating model</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="docs/img/design_implementation.svg"><img src="docs/img/build-process.svg" alt="2 · The process: spec approval, build/test/document, final human approval and session close" width="100%"></a>
      <p><a href="docs/GUIDE.md">Developer guide</a> · <a href="design/README.md">Design iterations</a></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="#how-an-answer-is-produced"><img src="docs/img/build-runtime.svg" alt="3 · The running system: validated tasks, checked evidence and separate operator surfaces" width="100%"></a>
      <p><a href="docs/answer-quality-status.md#what-executes-now">Runtime details</a> · <a href="PRD.md">Product and architecture spec</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="docs/modules/README.md"><img src="docs/img/build-milestones.svg" alt="4 · Modules and status: M1–M8 baseline delivered; later repairs implemented; quality review pending, M9 open, Stage 5 unstarted" width="100%"></a>
      <p><a href="docs/modules/README.md">Implementation notes</a> · <a href="context/PROJECT.md">Milestones and acceptance status</a></p>
    </td>
  </tr>
</table>

The UI evolved from an engineering spike through subsequent design iterations;
the repository does not claim the original implementation was design-first.
Historical module completion and current answer-quality acceptance are tracked
separately.

## Run locally

The current local route uses Python, Node, Java/Spark for batch preparation,
PostgreSQL/pgvector and a configured model endpoint. A fresh clone includes code,
a **40-row sample and authored documents**; the operationalized review corpus,
Delta lake, vector store, model cache and secrets are excluded.

1. Follow the **[local setup guide](data-pipeline-setup/local/LOCAL_SETUP.md)** to
   install dependencies and configure your own ignored `backend/.env` from
   [the template](backend/.env.example).
2. Prepare the real data and indexes as described there, then start the API and UI.
   Spark/ETL and embedding are preparation steps; reuse the prepared stores for
   subsequent application launches.
3. Open the frontend at `http://localhost:5173` and try the questions above using
   an appropriate demo role.

Local inference and embeddings can avoid hosted API charges, but require model
downloads and suitable hardware. Azure/OpenRouter generation is optional and
explicitly cost-gated. Docker Compose currently supplies PostgreSQL; a complete
one-command application package is not yet provided.

For development without loading the corpus, use the
[isolated test instructions](docs/testing/unit-testing.md). To reproduce the
AI-assisted build method, read [the developer guide](docs/GUIDE.md) and
[orchestrator contract](CLAUDE.md). Optional cloud setup and spending records live in
[the cloud runbook](data-pipeline-setup/cloud/CLOUD_SETUP.md) and [COST.md](COST.md).

## Further reading

| You want to… | Read |
|---|---|
| Understand the full product intent | [PRD](PRD.md) |
| Inspect evidence coverage, repairs and known failures | [Quality report](docs/answer-quality-status.md) |
| Trace implementation decisions | [Module notes](docs/modules/README.md) · [Decisions](context/DECISIONS.md) |
| Explore the interface design | [Design history](design/README.md) |
| Understand evaluation and model selection | [Acceptance artifacts](docs/testing/acceptance/README.md) · [Model study](docs/model-comparison.md) |
| Extend or resume development | [Developer guide](docs/GUIDE.md) · [Current task](context/CURRENT_TASK.md) · [Resume handoff](context/RESUME_NEXT_SESSION.md) |
