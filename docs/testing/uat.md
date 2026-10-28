# UAT — user acceptance testing

Human, scenario-based testing: a person drives real queries through the running
system and checks **expected vs. actual** behaviour. It is the acceptance level in
`.claude/rules/testing.md` (owner: human, at CHECKPOINT 2). It finds
design/behaviour defects that unit and SIT tests miss.

**Not the same as M7 Evaluation.** UAT is qualitative ("does the support role get a
cited policy answer?"). M7 is the automated quantitative gate (recall@k, MRR,
faithfulness, cost, latency) — see `backend/eval/` and `docs/modules/M7_evaluation.md`.

**Curated query battery:** the per-capability acceptance cases, their pass conditions,
a runner, and captured evidence live in `docs/testing/acceptance/` (`cases.md`,
`run_acceptance.py`, `RESULTS.md`).

## How to run it ($0, free mode)

```bash
cd backend && source .venv/bin/activate
export DATABASE_URL=postgresql://rag:rag@localhost:5432/rag PROVIDER_MODE=free
python -m retrieval.index_reviews && python -m retrieval.index_docs   # once
uvicorn app.main:app --reload       # then POST /query, or call agents.pipeline.answer()
```

Each result carries an **audit record** (intent, tool_path, sources, tokens, cost,
latency, grounding, memory) — read it to see *why* an answer came out the way it did.
Record every session in `uat-log.md`.

## Capability verification matrix

Every RAG concept implemented so far, where it lives, how it was checked by hand, and
its honest status. Legend: ✅ verified · ◑ partially · ○ not yet exercised · 🐞 defect.

| Capability | Module | Where | How checked (UAT) | Status |
|---|---|---|---|---|
| Intent routing (rule-first) | M4 | `agents/router.py` | after D-2 fix, high-confidence patterns win deterministically; LLM only for ambiguous cases. AC-1/AC-2→sql, AC-6→sql_rag on every run | ✅ verified (D-2 fixed 2026-10-28) |
| Hybrid retrieval (vector + BM25 + RRF) | M4.2 | `retrieval/hybrid.py` | review_rag & docs_rag return ranked, cited hits through the hybrid path | ◑ exercised end-to-end; fusion-vs-single not isolated |
| Reranking | M4.2 | `retrieval/rerank.py` | `reranker="none"` by default — not active in this run | ○ implemented, off by default |
| Access control (policy, pre-LLM) | M6 | `governance/policy.py`, `vector_store.build_where` | `marketing` out-of-scope → empty; unknown role → `AccessDenied`; `support` now reads docs | ✅ enforced (D-1 fixed 2026-10-28) |
| PII redaction | M2.3 / M6 | `governance/pii.py` | live `[EMAIL]` scrub visible in review answers | ✅ verified |
| Grounding / citation guard | M6 | `governance/grounding.py`, `agents/composer.py` | extractive answers fully cited; LLM drafts with uncited lines **blocked** → safe fallback | ✅ verified (both paths) |
| Auditability | M6 | `governance/audit.py` | full audit record returned per query | ✅ verified |
| Conversation memory | M5 | `memory/*` | 3-turn thread: `history_turns_used` 0 → 2 → 4 | ✅ verified |
| Persistent memory (cross-thread) | M5 | `memory/manager.py`, `user_memory` | preference set in thread A recalled in fresh thread B; findings stored scope-filtered | ✅ verified |
| Text-to-SQL agent | M4.4 | `agents/sql_agent.py` | "average rating for Electronics" → DuckDB → *"3.67 [1]"* | ✅ verified |
| Composer (LLM prose) | M4 | `agents/composer.py` | cited LLM prose produced (2.3); on weak drafts, guard falls back to extractive | ✅ verified (model-dependent fluency) |
| Evaluation gate | M7 | `backend/eval/*` | `python -m eval.run_eval` → all 6 metrics PASS | ✅ verified |

**Status:** D-1, D-2, D-3 all fixed and re-verified 2026-10-28 (see
`docs/testing/acceptance/RESULTS.md`). One hygiene item open — **H-1**: tests share the
demo's pgvector DB and can wipe the review index; isolate it before M8. A stronger model
(`qwen2.5:3b` or Azure) raises how often LLM prose clears the citation guard — the guard
itself is verified either way.
