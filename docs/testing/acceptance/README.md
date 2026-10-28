# Pipeline acceptance & quality testing

A curated battery of **queries** that validate — with evidence — that every RAG
capability we built (M1–M7) actually works, is accurate, and is reliable, **before**
we move to the end-to-end app (M8). Each query targets a specific capability and has
explicit **pass conditions**; results and our read of them are recorded with evidence.

## What to call this

It is **acceptance & quality testing** of the whole pipeline — UAT-style (human,
scenario/query-driven, evidence + judgement), but broader than one scenario. It sits
alongside the other levels, not instead of them:

| Level | Scope | Here |
|---|---|---|
| Unit | one function, mocked | `backend/tests/` (developer) |
| SIT | components wired + one smoke | `docs/testing/sit.md` (tester) |
| **Acceptance & quality (this folder)** | **the full pipeline, per capability, with evidence** | **human** |
| Evaluation (M7) | automated metric gate (recall@k, MRR, faithfulness, cost, latency) | `backend/eval/` |

## Files

- `cases.md` — the catalogue: every test case (capability · query · role · expected ·
  pass conditions).
- `run_acceptance.py` — runs the cases against the live pipeline and prints evidence.
- `RESULTS.md` — the captured run: actual output per case, verdict, and our decisions.

## How to run ($0, free mode)

```bash
cd backend && source .venv/bin/activate      # uses backend/.env (pgvector + Ollama)
python ../docs/testing/acceptance/run_acceptance.py
```
Prerequisites: pgvector up (`docker compose -f infra/docker-compose.yml up -d`), the
index built (`python -m retrieval.index_reviews && python -m retrieval.index_docs`), and
Ollama running with `llama3.2:3b` for the LLM paths.

## Conditions to check in every result

A generic checklist — read each response's `answer` + `audit` against these:

| # | Condition | Where to look |
|---|---|---|
| C1 | **Routing** — did it pick the right tool for the question type? | `audit.intent` |
| C2 | **Tool path** — SQL for aggregates, retrieval for meaning, both for "why" | `audit.tool_path` |
| C3 | **Grounding** — `path` is `llm` or `extractive`; `issues` empty or a justified block | `audit.grounding` |
| C4 | **Citations** — every claim cited; labels map to real sources; no citation to an unlisted number | `answer`, `citations` |
| C5 | **Access control** — retrieved `sources` stay inside the role's allowed categories; out-of-scope → empty; unknown role → denied | `audit.sources`, errors |
| C6 | **PII** — no raw email/phone/name in the answer; redaction tokens (`[EMAIL]`) where expected | `answer` |
| C7 | **Hybrid** — vector-only and keyword-only rankings differ, and the fused list blends both | retrieval evidence (AC-11) |
| C8 | **Reranking** — with `RERANKER=local`, order/scores change vs `none` | retrieval evidence (AC-12) |
| C9 | **Memory** — `history_turns_used` grows within a thread; preferences recalled across threads | `audit.memory` |
| C10 | **Cost / latency** — `cost_usd` = 0 in free mode; `latency_ms` within a sane bound | `audit` |
| C11 | **Accuracy** — numeric answers match a hand-computed ground truth | `answer` vs known data |

Status legend used in `RESULTS.md`: ✅ pass · ⚠️ pass with caveat · ❌ fail (→ defect).
