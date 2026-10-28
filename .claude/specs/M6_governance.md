# Spec M6: Governance

## User story
As a security/compliance owner of the copilot, I want role-based access enforced at
retrieval (before the LLM), PII redacted, uncited claims blocked, and every answer
recorded in a durable audit log, so that an executive and a support agent provably see
different evidence, no personal data leaks, no ungrounded claim is served, and any answer
can be reconstructed after the fact. Everything runs in both provider modes (`azure|free`)
and at $0 / no cloud spend — policy, redaction, grounding and audit are all local.

## Module intent & integration with M4/M5
M6 tightens five hooks the earlier modules deliberately left open, with **no new infra**
(reuses the pgvector Docker Postgres, `Settings`/pydantic-settings, `CostLedger`, the
provider-adapter, and `build_where` as the single retrieval choke point). New code lives in
`backend/governance/` (PRD §11) as the single home for access policy, PII and audit.

- M4 `derive_scope(role)` returns `{}` (OPEN) for every role — M6 gives it a real policy.
- M4 `build_where`/`check_citations` already exist as the retrieval choke point and grounding
  check — M6 feeds them the policy and promotes grounding to a first-class tested control.
- M5 stamps a `scope` JSONB on each `user_memory` row and keys reads by `user_id`, but
  (a) does not filter memory reads by role scope and (b) `append_message` lacks the owner
  check `recent_messages`/`load` already have — M6 closes both.
- M2/M5 share a US/NANP-only phone regex — M6 hardens it (UK/intl) from one source of truth.
- `pipeline.answer` already emits an `audit` dict (query, role, tool_path, sources, tokens,
  cost, latency, grounding, memory) — M6 persists it durably.

## Module acceptance criteria
- [ ] A real `role → permitted sources/categories` policy drives `derive_scope(role)`; an
      executive scope and a support scope differ, and the difference is enforced in the SQL
      `WHERE` via `build_where` (before any LLM call). An unknown/empty role is denied (typed error).
- [ ] Memory reads are filtered by the role's scope (using the stamped `scope` JSONB) so a
      finding learned under one scope is not surfaced to a role outside it; the memory
      write/persist path verifies the caller owns the `thread_id`.
- [ ] PII redaction uses one shared, hardened pattern set (email + UK/intl/US phone) at
      ingestion (`silver.py`) and in memory writes, and generated answers are scrubbed before
      they leave the composer (no PII leaks via an LLM draft).
- [ ] Uncited / dangling-citation drafts are blocked by a first-class, tested grounding gate;
      a failing draft never reaches the user (the grounded extractive answer is served instead).
- [ ] A durable `audit_log` row is written per answer (query, role, intent, tool_path, sources,
      tokens, cost, latency, grounding, memory); writing it never fails the turn.
- [ ] `ruff`/`black` clean on `backend/governance/` and all changed files; $0, no cloud spend.

## Sub-modules (ordered, each build → verify → integrate)

### M6.1 Access policy + retrieval enforcement
- Goal: replace the OPEN `derive_scope` stub with a real role→source/category policy that
  flows into `build_where` before the LLM.
- Acceptance criteria:
  - [ ] `scope_for_role(role) -> Filters` returns an unrestricted `{}` for full-access roles
        (e.g. `executive`, `admin`) and a restricting `Filters` (e.g. `{"category": [...]}` and/or
        `{"source": ...}`) for scoped roles (e.g. `support`, `marketing`); an unknown/empty role
        raises `AccessDenied`. `executive` scope ≠ `support` scope.
  - [ ] `marketing` scope is `{"category": ["Electronics", "Beauty_and_Personal_Care",
        "Toys_and_Games"]}` — it includes `Electronics` so the PRD §2 marketing persona's
        flagship question (complaints about *wireless earbuds* = Electronics) resolves in-scope.
        Marketing and `support` overlap only on `Electronics`; the two scoped roles stay
        distinct otherwise (see the 2026-10-28 ADR in `context/DECISIONS.md`).
  - [ ] `router.derive_scope(role)` delegates to `scope_for_role`; the returned scope only uses
        keys in `FILTER_COLUMNS` (`source_type`/`source`/`category`) so `build_where` accepts it,
        and `source_type` pinning in the agents still wins over a scope key (unchanged).
  - [ ] Unit tests prove two roles yield different `WHERE` params through `build_where`, and a
        denied role raises; `pipeline.answer` maps `AccessDenied` to a typed `PipelineError` (502),
        never an unhandled 500.
- Build steps:
  1. `backend/governance/__init__.py`, `backend/governance/policy.py`: `Role`,
     `ACCESS_POLICY: dict[str, Filters]`, `AccessDenied(Exception)`, `scope_for_role(role)`.
  2. Point `agents/router.py::derive_scope` at `scope_for_role`; catch `AccessDenied` in
     `pipeline.answer`'s existing upstream-failure block (→ `PipelineError`).
- Files to touch: `backend/governance/__init__.py`, `backend/governance/policy.py`,
  `backend/agents/router.py`, `backend/agents/pipeline.py`, `backend/tests/test_access_policy.py`.
- Integration point: consumes M4's `Filters`/`build_where`; the policy is the single source the
  retrieval and SQL agents already read via `decision.scope`.

### M6.2 Memory access enforcement + thread ownership
- Goal: apply the role policy to memory reads and add the missing owner check on the write path.
- Acceptance criteria:
  - [ ] `MemoryManager.load(thread_id, user_id, role, ...)` filters `user_memory` by the role's
        scope: a `finding` whose stamped `scope` names a category outside the role's permitted set
        is not returned (reads already filtered by `user_id` remain so). A full-access role sees all.
  - [ ] `MemoryStore.append_message(thread_id, role_kind, content, *, user_id)` verifies the thread
        belongs to `user_id` (same ownership subquery `recent_messages` uses); a non-owner write
        raises and persists nothing. `MemoryManager.persist(...)` passes `user_id` through.
  - [ ] Unit tests: a scoped role gets a filtered finding list; a non-owner `append_message` raises;
        scope filtering is done in the query/`MemoryStore`, not by post-filtering in Python only.
- Build steps:
  1. `backend/memory/store.py`: add `user_id` owner check to `append_message`; add an optional
     scope filter to `list_memory` (JSONB containment on the stamped `scope`, e.g. category overlap).
  2. `backend/memory/manager.py`: `load`/`persist` take `role`, call `scope_for_role`, pass the
     scope to `list_memory` and `user_id` to `append_message`.
  3. `backend/agents/pipeline.py`: thread `role` into `_load_context`/`persist` (already has `role`).
- Files to touch: `backend/memory/store.py`, `backend/memory/manager.py`,
  `backend/agents/pipeline.py`, `backend/tests/test_memory_access.py`.
- Integration point: consumes M6.1 `scope_for_role`; reuses the M5 `scope` JSONB column and the
  per-call psycopg pattern; skip-with-reason if Postgres is unreachable (per `testing.md`).

### M6.3 PII redaction hardening (ingestion + generation)
- Goal: one hardened PII pattern set, reused everywhere, plus generation-time scrubbing.
- Acceptance criteria:
  - [ ] `backend/governance/pii.py` exports `EMAIL_PATTERN`/`PHONE_PATTERN` (strings) and
        `redact(text) -> str`; the phone pattern matches UK (`+44`, `0xxxx xxxxxx`) and other
        `+<cc>` international forms as well as the existing US/NANP forms, with a unit corpus
        (US, UK, intl, email) all redacted and plausible non-phone digit strings left intact.
  - [ ] `data/etl/silver.py` and `backend/memory/manager.py` both use these patterns (single
        source of truth — remove the copied regexes); Silver redaction behaviour is unchanged or
        broadened, never narrowed.
  - [ ] The composer scrubs the final answer (both LLM and extractive paths) through `redact(...)`
        before returning, so a PII string present in an LLM draft is removed; a unit test asserts it.
- Build steps:
  1. `backend/governance/pii.py` with hardened patterns + `redact`.
  2. `data/etl/silver.py`: import `EMAIL_PATTERN`/`PHONE_PATTERN` from `governance.pii` (backend is
     already importable there via `app.config`); keep `regexp_replace` usage.
  3. `backend/memory/manager.py`: import `redact`/patterns from `governance.pii`; drop local copies.
  4. `backend/agents/composer.py`: apply `redact(...)` to `answer` before building `AnswerResult`.
- Files to touch: `backend/governance/pii.py`, `data/etl/silver.py`,
  `backend/memory/manager.py`, `backend/agents/composer.py`, `backend/tests/test_pii.py`.
- Integration point: becomes the single PII choke point M2 and M5 referred to as "deferred to M6";
  generation-time scrub closes the leak path the LLM could otherwise open.

### M6.4 Citation / grounding gate
- Goal: promote the M4 citation check to a first-class, named, tested governance control.
- Acceptance criteria:
  - [ ] `backend/governance/grounding.py` exposes `enforce_grounding(answer, valid) -> list[str]`
        (dangling `[n]`, uncited claim lines, no-citation answers); `composer.check_citations` is
        replaced by / delegates to it with identical behaviour (M4 composer tests still pass).
  - [ ] A unit suite proves the gate blocks: a dangling citation, an uncited claim line, and a
        citation-free draft; and passes a fully-cited draft. Composer still discards a failing LLM
        draft and serves the grounded extractive answer, recording issues in `audit.grounding`.
- Build steps:
  1. `backend/governance/grounding.py`: move the `check_citations` logic; keep the `_CITE` regex.
  2. `backend/agents/composer.py`: import and call `enforce_grounding`.
- Files to touch: `backend/governance/grounding.py`, `backend/agents/composer.py`,
  `backend/tests/test_grounding.py`.
- Integration point: no behaviour change to the pipeline; this makes PRD §7 "uncited claims are
  blocked" an explicitly owned governance control the Tester/M7 can target.

### M6.5 Durable audit log store + wiring
- Goal: persist the `audit` dict `pipeline.answer` emits so any answer can be reconstructed.
- Acceptance criteria:
  - [ ] `audit_ddl()` creates `audit_log(id, created_at, query, role, intent, tool_path JSONB,
        sources JSONB, tokens, cost_usd, latency_ms, grounding JSONB, memory JSONB)` in the same
        Postgres; `AuditStore.record(audit: dict)` inserts one row; `get_audit_store()` factory.
  - [ ] `pipeline.answer` writes the audit row after the audit dict is finalised; a write failure
        is logged and swallowed (recorded but never raised) so it never fails the turn.
  - [ ] Unit test: `record` round-trips an audit dict; a second test proves a failing store does
        not break `answer`. Skip-with-reason if Postgres is unreachable.
- Build steps:
  1. `backend/governance/audit.py`: `audit_ddl()`, `AuditStore`, `get_audit_store()` (per-call
     psycopg like `MemoryStore`); add an `audit_enabled` + schema-ensure like `ensure_memory_schema`.
  2. `backend/agents/pipeline.py`: after `result.audit` is complete, best-effort
     `get_audit_store().record(result.audit)` in a guarded `to_thread` call.
  3. Settings: `audit_enabled` (bool, default true).
- Files to touch: `backend/governance/audit.py`, `backend/agents/pipeline.py`,
  `backend/app/config.py`, `backend/.env.example`, `backend/tests/test_audit_log.py`.
- Integration point: reuses the M5 Postgres + per-call connect pattern; consumes the existing
  `audit` dict unchanged (no new fields required from upstream).

## Test plan
- Per sub-module (scoped): M6.1 two roles → different `build_where` params + denied role raises;
  M6.2 scoped role gets filtered findings + non-owner write raises; M6.3 the PII corpus
  (US/UK/intl/email) is redacted and a draft PII string is scrubbed; M6.4 the gate blocks each
  failure class and passes a clean draft; M6.5 audit row round-trips and a failing store is harmless.
- Module-level end-to-end smoke (one real, non-mocked check; free path, local Postgres, no hosted
  model): index the tiny M3 slice, then `answer(query, role="executive", ...)` and
  `answer(query, role="support", ...)` and assert (1) their retrieved `sources` / scope differ,
  (2) the served answer carries citations and contains no PII, (3) an uncited LLM draft (simulated
  via a stub LLM) is blocked, and (4) an `audit_log` row exists for each call. $0.

## Security & cost notes
- **Expected cloud spend for M6 = $0; cap = $0 in CI.** Policy, memory enforcement, PII, grounding
  and audit are all local/Postgres. **CHECKPOINT 1 is also the cost go-ahead** and authorises only
  the $0 governance layer — no Azure/embedding/LLM spend is introduced by this module.
- Access control is enforced **in code at retrieval, before the LLM** (via `build_where`), and on
  memory reads/writes — never by prompting the model. Least privilege: unknown roles are denied.
- Secrets: `database_url` and the `PII_HASH_SALT` stay in `.env` only, never logged; the audit log
  stores redacted content and ids, not raw PII.

## Out of scope
- Prompt-template/model-identifier versioning (PRD §7 "Versioning") beyond what the audit dict
  already records — deferred; not required by this module's criteria.
- The retrieval/answer quality + cost/latency **evaluation gate** — that is M7.
- Any audit-log UI / dashboard and Azure Key Vault / managed identity wiring — M8 (serving/deploy).
- Redefining the M5 memory schema; M6 only adds an owner check + scope filter on existing tables.
