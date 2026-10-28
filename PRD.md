# Retail Customer Intelligence Copilot — Product Requirements Document

An enterprise agentic-RAG assistant that lets non-technical staff query a retailer's own customer, product and review data in natural language, and receive grounded, cited, access-controlled answers.

> **How this doc is structured.** This PRD is the stable *backbone* — the what & why, the architecture, and the module index. Detailed, changing requirements live per module in `.claude/specs/`; decisions and changes are logged in `context/DECISIONS.md`. To change a requirement, edit the relevant **spec** and log an ADR — don't grow this document. A new feature is added as a new module row (§10) + a new spec, so the project expands in small blocks.
>
> **Version 1.3 · Last updated 2026-10-27** (§5/§9: broad-on-both-layers data strategy, capped embed — see `context/DECISIONS.md`)

---

## 1. Overview

Retail teams sit on millions of reviews and transactional records they cannot read or query directly. The copilot exposes this data through a conversational interface backed by an agent that chooses the right retrieval strategy per question — structured analytics for metrics, semantic retrieval for meaning — and returns answers grounded in the underlying evidence with citations.

---

## 2. Users & use cases

| Persona | Representative question | Required capability |
|---|---|---|
| Support agent | "Is this headphone's disconnection a known issue, and the common fix?" | semantic retrieval over reviews, cited |
| Marketing / product | "Top 3 complaints about our wireless earbuds this quarter — is sentiment improving?" | themes (RAG) + trend (SQL) |
| Executive | "Which product categories have the worst rating-to-price ratio, and why?" | SQL analytics + RAG explanation |

---

## 3. Scope & non-goals

**In scope:** conversational Q&A over multi-turn threads; conversational memory (short-term history, long-term user preferences, a memory manager); structured analytics (text-to-SQL); semantic retrieval over reviews and policy/manual documents; role-based access; answer evaluation; auditability; cloud deployment.

**Optional / stretch:** a knowledge graph of product↔issue↔fix (and user↔preference) relationships for multi-hop recall, built only if time allows.

**Non-goals:** sales forecasting / predictive ML; real-time transactional writes; production-grade multi-tenant hardening; consumer-facing UI polish.

---

## 4. System architecture

A router classifies each question's intent and access scope, dispatches to the appropriate tool(s), and a composer merges results into a single grounded, cited answer. Aggregation questions are routed to SQL rather than RAG by design, to avoid numeric hallucination.

```
                 ┌─────────────┐
   user ──────▶  │   ROUTER    │  intent + access scope
                 └──────┬──────┘
          ┌─────────────┼───────────────┐
          ▼             ▼               ▼
    ┌───────────┐ ┌───────────┐  ┌────────────┐
    │ SQL agent │ │ review-RAG │  │  docs-RAG  │
    │ structured│ │ vector +   │  │ policies / │
    │ analytics │ │ keyword +  │  │ manuals    │
    └─────┬─────┘ │ rerank     │  └──────┬─────┘
          │       └─────┬──────┘         │
          └──────────┬──┴────────────────┘
                     ▼
              ┌────────────┐
              │  COMPOSER  │  grounded answer + citations + audit record
              └────────────┘
```

| Question type | Tool | Rationale |
|---|---|---|
| counts / averages / trends / top-N | SQL agent | exact, cheap, no hallucinated numbers |
| reasons / themes / "what are people saying" | review-RAG | meaning resides in free text |
| policy / warranty / how-to | docs-RAG | knowledge retrieval over documents |
| "why did metric X change?" | SQL + RAG | SQL quantifies it, RAG explains it |

**Build-time vs. query-time.** Ingestion, ETL and corpus embedding run once (build-time). A user query performs only: embed-query → vector/keyword search → rerank → generate. Retrieval over the index is sub-second; the LLM call dominates latency and cost. Heavy batch compute is never invoked per query.

**Conversation & memory.** The copilot is a multi-turn chat, so a *memory manager* wraps the loop: each turn it loads the thread's recent history (short-term) and the user's durable preferences / prior findings (long-term) into the router's context, and after answering decides what to persist (summarised) — under the same PII and access rules as retrieval. This is what lets a user refine results over successive turns. Detailed in module M5; the optional knowledge graph is an extension of this layer for multi-hop recall.

---

## 5. Knowledge base & data

Primary source: **Amazon Reviews 2023** (`McAuley-Lab/Amazon-Reviews-2023`), window **2019–2023**.

| Layer | Source | Scope | Rationale |
|---|---|---|---|
| Structured / SQL | Amazon Reviews 2023 | broad — 15 categories, ≤100k reviews/category | aggregation needs no embeddings; storage is cheap and all categories stay queryable |
| Review-RAG | same | broad — 15 categories, ≤15k reviews/category (per-category cap, ~225k max) | capped per category, not curated to a few: quality plateaus well before the cap, and `text-embedding-3-small` (optionally 512-dim) keeps the vector bulk small (~1.4 GB, ~0.5 GB at 512-dim); retrieval reliability comes from hybrid search + rerank (M4) and the eval gate (M7), not row count |
| Docs-RAG | authored company policies/manuals + FTC/EU public-domain policy + 3–5 manufacturer manual PDFs | ~15–25 documents | authored docs give a trustworthy evaluation ground-truth; PDFs exercise multi-format parsing |

Fields split cleanly: structured columns (`rating`, `price`, `category`, `verified_purchase`, `timestamp`) drive SQL; free-text (`title`, `text`, product `description`) drives RAG. Join keys: product (`ASIN`), user, time.

---

## 6. Retrieval pipeline

Ingest → parse (multi-format via Docling) → chunk + attach metadata → embed → **hybrid search (vector + BM25) → reciprocal-rank fusion → rerank** → grounded generation with inline citations → audit record.

Design elements beyond baseline RAG: metadata-filtered retrieval, hybrid search with reranking, sub-agents with isolated context for heavy document analysis, and citation enforcement on generated claims.

---

## 7. Governance: access, guardrails, auditability

| Control | Mechanism |
|---|---|
| Role-based access (who may see what) | role → permitted sources/categories enforced at retrieval, before generation (executive scope ≠ support scope) |
| Grounding | generated claims must map to retrieved evidence; uncited claims are blocked |
| PII / Responsible AI | redaction at ingestion; refusal and safe-completion rules at generation |
| Auditability | each answer records query, role, retrieved sources, tool path, tokens, cost, latency |
| Versioning | prompt templates and model identifiers pinned and logged per response |

---

## 8. Evaluation

| Dimension | Metric | Method |
|---|---|---|
| Retrieval quality | recall@k, MRR | labelled question→document set over authored docs |
| Answer quality | accuracy / faithfulness | LLM-as-judge against ground-truth |
| Cost | cost per query | per-call token accounting |
| Latency | p50 / p95 | request tracing |

Evaluation runs as a CI gate; regressions beyond thresholds fail the build.

---

## 9. Platform & infrastructure

| Concern | Service | Operating note |
|---|---|---|
| LLM + embeddings | Azure OpenAI | low TPM quota; small models; provider-adapter allows a free-tier fallback |
| Vector search | pgvector (bulk) + Azure AI Search (tiny demo slice) | pgvector holds the ~225k-review bulk; AI Search free tier (50 MB) is a demo slice only |
| Object storage | Azure Blob | cents per GB |
| Batch ETL | Databricks (medallion) | small auto-terminating cluster; batch only, never at query time |
| API | Azure Container Apps (FastAPI, async) | scale-to-zero |
| Web UI | Azure Static Web Apps (React) | free tier |
| CI/CD, IaC, observability | GitHub Actions, Bicep/Terraform, tracing | — |

Cost controls: budget alerts, in-code token/cost ceilings, teardown script, and `COST.md` tracking actual spend.

---

## 10. Delivery plan

Delivered incrementally as self-contained modules. Each module ships code, tests, and a short design note under `docs/modules/` recording decisions, problems encountered, fixes, and supporting visuals (diagrams/screenshots). A module is complete only when documented.

| # | Module | Outcome |
|---|---|---|
| 1 | Foundations | repo + IaC skeleton, config, budget alerts, cost tracking |
| 2 | Data ingestion & ETL | Databricks medallion pipeline → Delta + Blob |
| 3 | Indexing | embed curated review subset → vector store; parse docs → index |
| 4 | Retrieval & agents | router + SQL/review-RAG/docs-RAG agents + composer, hybrid + rerank |
| 5 | Conversation & memory | threads, short-term history, long-term user preferences, a memory manager (governed by PII + access rules) |
| 6 | Governance | role-based access, PII redaction, citation enforcement, audit log |
| 7 | Evaluation | metrics harness + CI gate |
| 8 | Serving & UI | FastAPI backend + React frontend deployed to Azure |
| 9 | Documentation | consolidated architecture diagrams and design record |

---

## 11. Repository structure

```
retail-intelligence-copilot/
├── PRD.md
├── COST.md
├── infra/                 # IaC (Bicep/Terraform)
├── data/                  # ETL jobs (Databricks / PySpark)
├── backend/
│   ├── agents/            # router, SQL, review-RAG, docs-RAG, composer
│   ├── retrieval/         # hybrid search, rerank, indexing
│   ├── governance/        # access policy, PII, audit
│   └── eval/              # metrics harness
├── frontend/              # React app
├── docs/
│   ├── architecture/      # diagrams
│   └── modules/           # per-module design & progress notes (with visuals)
└── .github/workflows/     # CI/CD
```
