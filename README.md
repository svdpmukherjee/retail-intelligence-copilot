# Retail Customer Intelligence Copilot

> An enterprise **agentic-RAG** assistant over a retailer's own review, product and
> policy data — returning answers that are **grounded, cited, and access-controlled**.

Ask a question in plain language; a **router** picks the right tool (structured
analytics, semantic review search, or policy lookup), retrieval runs **inside the
caller's access scope**, and a **composer** returns one answer where every claim is
cited. Every turn is audited. It runs **fully local at $0**, and the same code
switches to Azure behind one flag.

`Python · FastAPI · React · pgvector · Spark/Delta · Ollama ↔ Azure OpenAI`
 · full spec in **[`PRD.md`](./PRD.md)**

---

## 1 · How I run the build

One **orchestrator** directs six specialist AI sub-agents through a checkpointed
loop — the way a small engineering team ships. Commands trigger the work, rules
govern it, and context files carry memory between sessions.

![Operating model: a human-led orchestrator directing six specialist sub-agents, with commands, rules and context memory](docs/img/agentic_architecture.svg)

## 2 · The process

Every module follows the same loop — **spec → build → test → document → close** —
with two **human approval gates**. A design track runs beside it on demand and feeds
rebuilds. Nothing passes a gate on its own.

![The module development loop and the design track, each with human approval gates](docs/img/design_implementation.svg)

## 3 · The running system

The agentic-RAG pipeline for one question. Access policy is enforced **before the
LLM**; retrieval fuses vector + keyword results (RRF, optional rerank); the composer
**blocks any uncited claim**; and the whole turn is written to an audit log.

![Runtime architecture from frontend through governance, router, agents, retrieval, composer and audit](docs/img/end_to_end.svg)

## 4 · Modules & status

Nine modules, built one per session — eight **done**, documentation in progress.
Four concerns run across all of them; the roadmap (observability, cloud deployment)
is marked honestly.

![Module status board M1–M9 with cross-cutting concerns and the pending roadmap](docs/img/modules.svg)

---

## The data

Built on the **real [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023)**
corpus (McAuley-Lab) across **15 product categories**, plus a small authored
knowledge base. Reviewer identities are hashed at ingestion (PII redaction). Each
source feeds one of the three retrieval tools:

| Source | Served by | Scale |
|---|---|---|
| Reviews → **structured** table | SQL agent — aggregates & trends | 15 categories × up to **100K** = ~**1.5M rows** |
| Reviews → **review text** | Review-RAG — semantic search | 15 categories × up to **15K** = ~**225K passages** |
| **Policy & manuals** (authored) | Docs-RAG — policy Q&A | **22 docs** (18 markdown + 4 PDF) |

Built by a **medallion ETL** (Bronze → Silver → Gold, Delta) in Spark, then embedded
into pgvector.

---

## Run it from the beginning (Claude Code)

The whole system runs locally at **$0** — no cloud account required.

1. Clone the repo and install **[Claude Code](https://docs.claude.com/en/docs/claude-code)**.
2. Start local services: `docker compose -f infra/docker-compose.yml up -d` (Postgres + pgvector),
   and an [Ollama](https://ollama.com) model for the free LLM.
3. Open a session and skim **[`PRD.md`](./PRD.md)** (what) + **[`context/PROJECT.md`](./context/PROJECT.md)** (where we are).
4. Say **"build M1"** (or **"next"**). The orchestrator runs the loop and **stops for
   your approval** at each checkpoint — you can watch every phase.

Going to the cloud is optional and **cost-gated** (see [`COST.md`](./COST.md)); one
env flag swaps the free stack for Azure. New here? Start with **[`docs/GUIDE.md`](./docs/GUIDE.md)**.
