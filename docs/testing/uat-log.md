# UAT log

Dated record of human acceptance sessions. Newest at the top. One row per scenario;
findings and defects called out below each session. Verdict: PASS / PASS* (works with a
caveat) / FAIL.

---

## 2026-10-28 — Session 3: re-verify after D-1/D-2/D-3 fixes (free mode, $0)

Re-ran the full acceptance suite (`docs/testing/acceptance/run_acceptance.py`) after the
three `/change` fixes landed. Result: **13 ✅ · 3 ⚠️ · 0 ❌** — all defects closed.

- **D-1 ✅** — `support` now retrieves docs: AC-9 → 6 cited policy sections (was empty);
  reviews stay category-scoped (AC-7 marketing still empty). `test_rag_agents.py` 6/6.
- **D-2 ✅** — routing is rule-first: AC-2 → `sql` with a real GROUP BY ("3 reviews per
  category Books… Electronics"), AC-1 → `sql`, AC-6 → `sql_rag`. No more misroute.
- **D-3 ✅** — no `BinderException`/502 anywhere; generated SQL valid throughout.
- **H-1 (hygiene, OPEN):** review retrieval was empty at first — the `chunks` table had
  lost its 6 review rows (tests share the live DB). Rebuilt with `index_reviews` ($0);
  all review cases then passed. Recommend isolating the test DB before M8. See
  `docs/testing/acceptance/RESULTS.md`.

Details and evidence: `docs/testing/acceptance/RESULTS.md`.

---

## 2026-10-27 — Session 2: full suite with a local LLM (Ollama `llama3.2:3b`, free mode, $0)

Context: wired a free local LLM (Ollama) so the LLM-dependent paths run — text-to-SQL,
LLM intent routing, LLM-composed prose, the citation draft-rejection guard, and LLM
memory summaries. Same sample knowledge base. Each case: query → expected → actual.

### A. Routing & answers (one query per route)

| # | Query · role | Expected | Actual | Verdict |
|---|---|---|---|---|
| 2.1 | "How many reviews are there per category?" · analyst | route **sql**, counts per category | LLM **mis-routed to review_rag**; LLM draft self-rejected ("not enough information") → extractive reviews | FAIL → defect **D-2** |
| 2.2 | "What is the average rating for Electronics?" · executive | route **sql**, a number | **sql**; *"The average rating for electronics is 3.67 [1]"*, `grounding=llm`, cites SQL result | PASS |
| 2.3 | "What do customers say about build quality?" · support | **review_rag**, cited summary | *"Customers generally report positive experiences with a solid build quality [1]. However… dissatisfaction… [4]."* `grounding=llm` | PASS |
| 2.4 | "What is the return and refund policy?" · executive | **docs_rag**, cited policy | docs retrieved; LLM draft added uncited preamble → **citation guard blocked it** → safe extractive, correctly cited (refund 5–7 days, non-returnables, 30-day window) | PASS (guard fired as designed) |
| 2.5 | "Why did ratings drop for Electronics?" · analyst | **sql_rag**: numbers + review evidence | routed **sql_rag**, `tool_path=[sql_agent, review_rag]`; LLM draft blocked → extractive (SQL `rating=3.0` + 6 cited reviews) | PASS (routing + dual-tool); LLM prose blocked |

### B. Multi-stage conversation (one thread, role=support)

| # | Turn | Expected | Actual | Verdict |
|---|---|---|---|---|
| 2.6a | t1 "…build quality?" | fresh thread | `history_turns_used=0`, persisted 1, `grounding=llm` cited answer | PASS |
| 2.6b | t2 "and about battery life?" | loads t1 | `history_turns_used=2` (prior user+assistant loaded) | PASS |
| 2.6c | t3 "which sounds more positive?" | loads t1–t2 | `history_turns_used=4` | PASS |

### C. Persistent memory across threads (role=support)

| # | Step | Expected | Actual | Verdict |
|---|---|---|---|---|
| 2.7 | thread A: *"From now on, please always keep answers short."* | store a preference | `persisted=2` (preference + finding) | PASS |
| 2.8 | thread B (**new** thread, same user) | preference recalled in a fresh conversation | loaded `preferences=['From now on, please always keep answers short']`, `prior_findings=2` | PASS |

### Findings

- **D-2 (OPEN, defect):** the **LLM router mis-routed** a textbook aggregate ("how many …
  per category") to `review_rag` instead of `sql`. The keyword-rule fallback had routed
  the *same* query correctly in Session 1 — so the small model is **less reliable than the
  rules** for high-confidence aggregates. Fix options: let high-confidence rule matches
  override the LLM, or use a stronger model. The rule path is the safer default.
- **Observation (not a defect — the guardrail working):** `llama3.2:3b` often emits drafts
  that break the strict one-citation-per-line format (adds preamble/notes), so the
  **grounding guard rejects them and falls back to the cited extractive answer** (2.4, 2.5,
  2.6b). Safety holds every time; fluent LLM prose depends on a stronger model
  (`qwen2.5:3b`, or Azure) — swap `FREE_LLM_MODEL` to improve pass rate.
- **Verified working:** text-to-SQL (2.2), LLM-composed cited prose (2.3), citation
  draft-rejection guard (2.4, 2.5), conversation memory 0→2→4 (2.6), persistent
  cross-thread memory (2.8), and PII `[EMAIL]` redaction throughout.

### Next

1. Fix **D-1** (docs scoping) and **D-2** (LLM-vs-rule routing) via `/change`.
2. Try `FREE_LLM_MODEL=qwen2.5:3b-instruct` and re-run 2.1/2.4/2.5 to see the LLM prose
   clear the citation guard more often.

---

## 2026-10-27 — Session 1: first human test of M1–M7 (free mode, $0)

Context: M1–M7 built by the agent loop; this is the first hands-on test by the human
reviewer. Local sample knowledge base only (6 review chunks in Electronics +
Home_and_Kitchen; 79 doc chunks from 18 policies + 4 manuals). No LLM configured, so
answers are **extractive** (cited quotes), which still exercises routing, retrieval,
governance and memory.

| # | Scenario (query · role) | Route | Expected | Actual | Verdict |
|---|---|---|---|---|---|
| 1 | "…per category?" · analyst | sql | counts from structured table | `SQLGenerationUnavailable` (needs a model) | PASS* (clean, expected) |
| 2 | "average rating for Electronics" · executive | sql | aggregate | `SQLGenerationUnavailable` | PASS* (clean, expected) |
| 3 | "customers say about battery life" · support | review_rag | cited reviews, in scope | 6 cited reviews, Electronics/Home only; `[EMAIL]` redacted | PASS |
| 4 | "return and refund policy" · support | docs_rag | cited policy | **"No supporting evidence"** | FAIL → defect D-1 |
| 5 | "set up the laptop" · support | docs_rag | cited manual | **"No supporting evidence"** | FAIL → defect D-1 |
| 6 | "return and refund policy" · executive | docs_rag | cited policy | correct, 6 cited doc sections | PASS |
| 7 | "set up the laptop" · admin | docs_rag | cited manual | correct, cited setup steps | PASS |
| 8 | "why did ratings drop" · analyst | sql_rag | numbers + reviews | `SQLGenerationUnavailable` | PASS* (clean, expected) |
| 9 | "battery life" · marketing | review_rag | empty (out of scope) | empty — Beauty/Toys/Books scope | PASS |
| 10 | "battery life" · hacker | — | denied | `AccessDenied` (deny-by-default) | PASS |
| 11 | memory · support, 2 turns | review_rag | 2nd turn loads history | `history_turns_used` 0 → 2, persisted | PASS |
| 12 | M7 eval harness | — | all gates pass | recall@k 1.0, MRR 1.0, faithfulness 0.70, cost $0, p50 1133ms, p95 1249ms — **gate passed** | PASS |

### Findings

- **D-1 (OPEN, defect):** category-scoped roles (`support`, `marketing`) retrieve **zero
  documents**. `docs_rag` applies the role's `category` filter to doc chunks, but docs
  have no category (`category=NULL`), so `category = ANY([...])` excludes all of them.
  Proof: `docs_rag(q, no scope)` → 6 hits; `docs_rag(q, category=Electronics)` → 0 hits.
  Impact: the **support persona cannot read any policy/warranty/return/manual doc** — the
  main support use case. Fails *safe* (denies, never leaks) but over-denies.
  Fix (via `/change`, M6 × M4): docs should be scoped by `source`/doc-type, not product
  category; drop the `category` filter from the docs path.
- **Env note (not a defect):** `sql` / `sql_rag` need an LLM for text-to-SQL. They fail
  *clean* (typed `PipelineError`), as designed. Wire a free local LLM (Ollama) to exercise
  them and to see LLM-composed prose + the citation draft-rejection guard — still $0.
- **Positive:** PII redaction (`[EMAIL]`), access control (out-of-scope empty + unknown-role
  denied), full audit records, and conversation memory all verified live at $0.

### Next

1. Fix D-1 through `/change`, then re-run scenarios 4–5 (expect PASS).
2. Add Ollama; re-run scenarios 1, 2, 8 and spot-check LLM-composed answers; update the
   capability matrix ○/◑ rows in `uat.md`.
