# Spec M5: Conversation & memory

## User story
As a retail staff member holding a multi-turn conversation with the copilot, I want it to
remember the thread so far (short-term) and my durable preferences / prior findings
(long-term), and fold that into each new answer, so that I can refine results across turns
("and for earbuds?", "same but this quarter") without repeating myself — while my memory stays
under the same PII and access rules as retrieval. This runs at $0 on the free/local path
(summarisation has a deterministic fallback); the Azure LLM summariser sits behind the existing
provider seam, gated.

## Module intent & integration with M4
A **memory manager** wraps the M4 pipeline turn. Today `pipeline.answer(query, role)` is
single-shot: router → tool(s) → composer under one `CostLedger`, emitting an `audit` dict. M5
adds a per-query **memory context** seam (it does not exist yet — this spec creates it):

- **Before answering:** `answer(...)` loads the thread's recent history + the user's durable
  memory into a `MemoryContext` and threads it into `router.route(...)` (to resolve elliptical
  follow-ups) and `agents.composer.compose(...)` (so the answer is coherent with the thread).
- **After answering:** the manager appends the turn's messages and decides what durable memory
  to persist (summarised), reusing the M4 `audit` dict (sources, intent, scope) as its hook.
- **Governance:** memory is per-user (`user_id` is the natural scope key — a user loads only
  their own memory); persisted text is PII-redacted; persisted findings inherit the turn's
  retrieval scope. Full role→source enforcement and the durable audit-log store remain M6.

Storage: reuse the existing pgvector Postgres (Docker `infra/docker-compose.yml`). M5 adds three
plain relational tables (`threads`, `messages`, `user_memory`) — no embeddings; semantic/vector
memory recall and the knowledge graph are the documented stretch, out of scope here.

## Module acceptance criteria
- [ ] A **memory store** persists threads, their ordered messages, and per-user durable memory
      items in Postgres; a user can read/write only their own rows (keyed by `user_id`). $0 local.
- [ ] A **memory manager** `load(thread_id, user_id, *, limit)` returns a `MemoryContext`
      (recent history turns + durable preferences/prior findings); `persist(...)` appends the
      turn and writes any new durable memory, **PII-redacted**, inheriting the turn's scope.
- [ ] `pipeline.answer(query, role, *, thread_id=None, user_id=None)` loads context before
      routing, passes it into `route` and `compose`, persists after, and records a `memory`
      block in the `audit` dict (thread_id, history_turns_used, persisted count). A call with no
      `thread_id`/`user_id` behaves exactly like M4 (memory off) — backward compatible.
- [ ] Summarisation of durable memory goes through `get_llm()` wrapped in `CostLedger`; a
      **deterministic fallback** (no hosted model) produces a usable memory item at $0, so CI
      stays green and $0 like M4. Azure summariser stays gated behind `azure_llm_go_ahead`.
- [ ] `POST /query` accepts optional `thread_id`/`user_id` (creating a thread when absent) and
      returns them with the answer; a **real, non-mocked** two-turn end-to-end smoke (free path,
      local Postgres, no hosted model) shows turn 2 using turn 1's history. `ruff`/`black` clean
      on `backend/memory/` and changed `backend/agents/` files.

## Sub-modules (ordered, each build → verify → integrate)

### M5.1 Memory store (Postgres tables + repository)
- Goal: durable, per-user storage for threads, messages, and memory items — the primitive the
  manager builds on.
- Acceptance criteria:
  - [ ] `memory_ddl()` creates `threads(id, user_id, role, created_at)`,
        `messages(id, thread_id, turn, role_kind['user'|'assistant'], content, created_at)`, and
        `user_memory(id, user_id, kind['preference'|'finding'], content, scope JSONB, created_at)`,
        each with the right indexes (`messages` by `thread_id, turn`; `user_memory` by `user_id`).
  - [ ] `MemoryStore` supports `create_thread`, `append_message`, `recent_messages(thread_id, limit)`
        (newest-N, returned oldest-first), `add_memory`, `list_memory(user_id, *, kind=None, limit)`.
        Every read/write is parameterised and filtered by `user_id`/`thread_id` (no cross-user reads).
  - [ ] Connects per call via `psycopg` using `settings.database_url` (mirrors `PgVectorStore`);
        `get_memory_store()` factory. Unit tests seed + read back; skip-with-reason if Postgres
        is unreachable (per `testing.md`), never a silent PASS.
- Build steps:
  1. `backend/memory/__init__.py`, `backend/memory/schema.py` (`memory_ddl()`, table/column
     constants, `ThreadRow`/`MessageRow`/`MemoryRow` pydantic models).
  2. `backend/memory/store.py`: `MemoryStore` (per-call connect like `PgVectorStore._connect`),
     `get_memory_store()`.
- Files to touch: `backend/memory/__init__.py`, `backend/memory/schema.py`,
  `backend/memory/store.py`, `backend/tests/test_memory_store.py`.
- Integration point: reuses M1 `Settings.database_url` and the M3/M4 per-call psycopg pattern;
  tables live in the same Postgres as `chunks` but are independent of it.

### M5.2 Memory manager — load path + MemoryContext seam
- Goal: assemble the per-query `MemoryContext` and wire it through router + composer so a turn
  "sees" the conversation.
- Acceptance criteria:
  - [ ] `MemoryContext` (pydantic): `thread_id`, `history: list[Turn]` (recent user/assistant
        pairs), `preferences: list[str]`, `prior_findings: list[str]`, plus `render() -> str`
        (a short, bounded text block ≤ `memory_history_turns` turns).
  - [ ] `MemoryManager.load(thread_id, user_id, *, limit)` reads `recent_messages` +
        `list_memory` and returns a `MemoryContext`; an empty/unknown thread yields an empty
        context (no error). History length is capped by `memory_history_turns`.
  - [ ] `route(query, role, ledger, *, context=None)` and `compose(query, sql_result, hits,
        ledger, *, context=None)` accept the optional context and, when present, prepend
        `context.render()` to the LLM `user` message (and the composer's extractive path ignores
        it — grounding/citation rules unchanged: memory never becomes a cited source). When
        `context=None`, behaviour is byte-for-byte the M4 path.
- Build steps:
  1. `backend/memory/manager.py`: `Turn`, `MemoryContext`, `MemoryManager.load(...)`.
  2. Add `context` kwarg to `agents/router.py` `route` and `agents/composer.py` `compose`,
     threading `context.render()` into the existing `user`-message strings only.
  3. Settings: `memory_history_turns` (default 6).
- Files to touch: `backend/memory/manager.py`, `backend/agents/router.py`,
  `backend/agents/composer.py`, `backend/app/config.py`, `backend/.env.example`,
  `backend/tests/test_memory_manager.py`.
- Integration point: consumes M5.1 `MemoryStore`; the `context` kwarg is additive and
  default-`None`, so M4 tests and the $0 path are unaffected.

### M5.3 Memory manager — persist path + summarisation (governed, $0 fallback)
- Goal: after a turn, append its messages and decide what durable memory to persist, summarised,
  PII-redacted, scope-stamped.
- Acceptance criteria:
  - [ ] `MemoryManager.persist(thread_id, user_id, query, result, ledger, *, scope)` appends the
        user query + assistant answer as messages, then persists at most one `finding` memory
        item summarising the turn (keyed to the turn's `audit` sources/intent) and any detected
        durable `preference`. Returns a count of items persisted.
  - [ ] Summarisation: when `get_llm().available`, summarise via `complete(...)` wrapped in the
        passed `CostLedger` (capped by `memory_summary_max_tokens`); otherwise a **deterministic**
        summariser (first grounded sentence(s) of the answer, truncated) — $0, no hosted model.
  - [ ] Persisted `content` is **PII-redacted** before write (reuse M2's redaction regex/util for
        email/phone; no raw `user_id`); the stored `scope` JSONB = the turn's retrieval scope, so
        a finding can never be surfaced outside the scope it was learned under (M6 enforces reads).
        `memory_max_items` caps durable rows per user (oldest trimmed).
- Build steps:
  1. Extend `backend/memory/manager.py` with `persist(...)`, `_summarise(...)` (LLM + fallback),
     `_redact(...)` (import/share M2 `redact`-style helper; if not importable, a local regex util).
  2. Settings: `memory_summary_max_tokens` (default 256), `memory_max_items` (default 20),
     `memory_enabled` (bool, default true).
- Files to touch: `backend/memory/manager.py`, `backend/app/config.py`, `backend/.env.example`,
  `backend/tests/test_memory_manager.py`.
- Integration point: reads the M4 `AnswerResult.audit` (sources/intent) and `RouteDecision.scope`
  as its inputs; all LLM spend flows through the existing `CostLedger` cap, same gate as M4.

### M5.4 Pipeline + API integration + end-to-end smoke
- Goal: make the turn memory-aware end to end and expose it through the API.
- Acceptance criteria:
  - [ ] `answer(query, role, *, thread_id=None, user_id=None)`: when both are set (and
        `memory_enabled`), it `load`s context → passes it to `route`/`compose` → `persist`s after,
        and adds `audit["memory"] = {thread_id, history_turns_used, persisted}`. When either is
        absent, it is the unchanged M4 single-shot path.
  - [ ] `POST /query` accepts optional `thread_id`/`user_id`; if `user_id` is given with no
        `thread_id`, a thread is created and both ids are returned in the response. Upstream
        failures remain typed `HTTPException` (502/500), never an unhandled 500.
  - [ ] A real two-turn smoke (free path, local Postgres, no hosted model): turn 1 answers and
        persists; turn 2 on the same thread shows turn 1 in the loaded `MemoryContext` and the
        `audit.memory.history_turns_used > 0` — non-mocked, $0.
- Build steps:
  1. Update `backend/agents/pipeline.py` `answer(...)` signature + load/persist calls (guarded so
     a memory failure degrades to a plain answer, logged in audit, never a 500).
  2. Update `backend/app/main.py` `QueryRequest`/response for optional `thread_id`/`user_id`.
  3. `backend/tests/test_pipeline_memory.py`: the two-turn smoke + the memory-off backward-compat case.
- Files to touch: `backend/agents/pipeline.py`, `backend/app/main.py`,
  `backend/tests/test_pipeline_memory.py`.
- Integration point: ties M5.1–M5.3 into the existing `answer` orchestration and `POST /query`;
  full UI/threads panel is M8.

## Test plan
- M5.1: unit — seed a thread + messages + memory, read back `recent_messages` (order + cap) and
  `list_memory` filtered by `user_id`; a second user's id returns none. Skip-with-reason if no DB.
- M5.2: unit — `load` on empty thread → empty context; on a seeded thread → bounded history;
  `route`/`compose` with `context=None` match M4 output, with context the render block is included
  in the LLM `user` payload (assert via a stub LLM) and memory is never added as a citation.
- M5.3: unit — `persist` appends two messages and ≤1 finding; deterministic summariser runs at $0
  with no LLM; persisted content has email/phone redacted and carries the turn's `scope`;
  `memory_max_items` trims oldest.
- M5.4: unit — memory-off call equals M4 behaviour; audit has no/empty memory block.
- Module end-to-end smoke (the one real check): `provider_mode=free`, local Postgres, no hosted
  model — index the tiny M3 slice, then two `answer(...)` calls on one `thread_id`/`user_id`;
  assert turn 2's `audit.memory.history_turns_used > 0` and a durable item was persisted, at $0,
  non-mocked. (If a local LLM endpoint is set it exercises the summariser; else the deterministic
  path still persists a grounded memory item.)

## Security & cost notes
- **Expected cloud spend for M5 = $0; cap = $0 in CI.** Default path: deterministic summariser +
  local Postgres, no cloud call. CHECKPOINT 1 is also the cost go-ahead: it authorizes committing
  only the $0 memory layer — **not** any Azure LLM summariser call.
- **Gated path:** the Azure LLM summariser runs only with keys + `azure_llm_go_ahead=true`
  (reuses the M4 gate); every summary call is bounded by `CostLedger`
  (`memory_summary_max_tokens`, `max_cost_usd`) and logged in `COST.md` — a few cents at most.
- **Access control:** memory is per-user (reads filtered by `user_id`); persisted findings carry
  the turn's retrieval `scope` in a `scope` JSONB column so they can never be surfaced outside it.
  M5 wires this hook; M6 enforces role→scope on memory reads just as it does for retrieval.
- **PII:** durable memory `content` is redacted at write (reuse M2's redaction); no raw `user_id`
  or reviewer PII is stored; memory is never injected as a citable source (grounding rules intact).
- **Secrets:** `database_url` / LLM keys via `.env` only (M1 keys reused), never logged.

## Out of scope
- **Full role→source access enforcement on memory reads + the durable audit-log store — M6.** M5
  stamps scope and keys by user but does not tighten `derive_scope`.
- **Evaluation gate (memory's effect on answer quality, cost/latency thresholds) — M7.**
- **Semantic / vector memory recall and the product↔issue↔fix / user↔preference knowledge graph —
  documented PRD §3 stretch, not built here.** M5 memory is relational + recency/preference, not
  embedded retrieval.
- **React chat/thread UI and Azure deployment — M8.** M5 exposes only the extended `POST /query`.
- Any Azure OpenAI call (summariser is gated, go-ahead only).
