# PROJECT.md — module status

Session-continuity file. The orchestrator reads this at session start and
updates it at session end. One row per module (see `PRD.md §10`).

| ID | Module | Status |
|----|--------|--------|
| M1 | Foundations (repo, IaC skeleton, config, budget alerts, cost tracking) | DONE |
| M2 | Data ingestion & ETL (Databricks medallion → Delta + Blob) | DONE |
| M3 | Indexing (embed review subset → vector store; parse docs → index) | DONE |
| M4 | Retrieval & agents (router + SQL/review-RAG/docs-RAG + composer) | DONE |
| M5 | Conversation & memory (threads, short/long-term memory, memory manager) | DONE |
| M6 | Governance (access policy, PII redaction, citations, audit log) | DONE |
| M7 | Evaluation (metrics harness + CI gate) | DONE |
| M8 | Serving & UI (FastAPI + React, deploy to Azure) | DONE |
| M9 | Documentation (architecture diagrams + consolidated design record) | TODO |

Status values: TODO → IN PROGRESS → DONE.
