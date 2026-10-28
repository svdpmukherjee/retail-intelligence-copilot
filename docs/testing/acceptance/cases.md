# Acceptance case catalogue

Every case targets one capability. "Checks" are the specific pass conditions (see the
generic C1–C11 list in `README.md`). Run them with `run_acceptance.py`; evidence and
verdicts land in `RESULTS.md`.

Knowledge base under test = the M2 **sample**: 6 review chunks (Electronics,
Home_and_Kitchen) + 79 doc chunks (18 policies + 4 manuals). Small on purpose — this
validates *mechanism and correctness*, not scale.

## Routing & answer quality

| ID | Capability | Query · role | Expected | Checks |
|---|---|---|---|---|
| AC-1 | Text-to-SQL (aggregate) | "What is the average rating for Electronics?" · executive | `intent=sql`; a single number that matches the data | C1, C2, C4, C11 |
| AC-2 | Text-to-SQL (group-by count) | "How many reviews are there per category?" · analyst | `intent=sql`; per-category counts from the structured table (not a count of retrieved snippets) | C1, C2, C11 |
| AC-3 | Review RAG (semantic) | "What do customers say about build quality?" · support | `intent=review_rag`; cited review summary | C1, C3, C4 |
| AC-4 | Docs RAG (policy) | "What is the return and refund policy?" · executive | `intent=docs_rag`; cited policy sections | C1, C3, C4 |
| AC-5 | Docs RAG (manual how-to) | "How do I set up the laptop?" · admin | `intent=docs_rag`; cited manual steps | C1, C3, C4 |
| AC-6 | sql_rag (why a metric moved) | "Why did ratings drop for Electronics?" · analyst | `intent=sql_rag`; `tool_path=[sql_agent, review_rag]`; numbers + review evidence | C1, C2, C4 |

## Governance & safety

| ID | Capability | Query · role | Expected | Checks |
|---|---|---|---|---|
| AC-7 | Access control — out of scope | "What do customers say about battery life?" · marketing | empty — marketing is scoped to Beauty/Toys/Books; no Electronics reviews reachable | C5 |
| AC-8 | Access control — unknown role | "…battery life?" · hacker | denied (`AccessDenied`), no data | C5 |
| AC-9 | Access control — scoped role + docs (D-1) | "What is the return and refund policy?" · support | **should** return the cited policy | C1, C4, C5 |
| AC-10 | PII redaction | "What do customers say about build quality?" · support | answer contains `[EMAIL]`, no raw email address | C6 |

## Retrieval mechanics

| ID | Capability | Probe | Expected | Checks |
|---|---|---|---|---|
| AC-11 | Hybrid search (vector + BM25 + RRF) | compare vector-only, keyword-only, and fused rankings for one review query | the two single-mode rankings differ; the fused list blends both | C7 |
| AC-12 | Reranking | same fused hits through `none` vs `local` cross-encoder | `local` changes order and attaches cross-encoder scores | C8 |

## Conversation & memory

| ID | Capability | Probe | Expected | Checks |
|---|---|---|---|---|
| AC-13 | Short-term conversation memory | 3 turns in one thread (support) | `history_turns_used` grows 0 → 2 → 4 | C9 |
| AC-14 | Persistent memory (cross-thread) | set a preference in thread A, open fresh thread B as the same user | the preference is loaded into thread B | C9 |

## Cross-cutting

| ID | Capability | Probe | Expected | Checks |
|---|---|---|---|---|
| AC-15 | Auditability | any answer | `audit` carries intent, tool_path, sources, tokens, cost_usd, latency_ms (+ memory when threaded) | C10 |
| AC-16 | Evaluation gate (M7) | `python -m eval.run_eval` | all six metrics pass their thresholds | C11 |
