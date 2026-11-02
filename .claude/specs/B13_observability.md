# Spec B-13: Observability plane (Langfuse tracing)

> Productionization-plane `/change` item, not a numbered PRD module. Approved Option A
> (central span seam in `pipeline.answer()`, agents untouched) — see the B-13 ADR in
> `context/DECISIONS.md` (2026-11-02) for the decision and the rejected alternatives.

## User story
As an **operator** debugging the copilot, I want a span-level view of each turn as it moves
through the pipeline (router → SQL → retrieval → composer), with per-stage timing and
token/cost attribution, so I can see *why* routing/latency/cost behaved a certain way without
reconstructing the path from raw `audit_log` rows by hand. This is an **operator plane only**:
it is off by default, never on the per-query latency path, carries no PII, and nothing from it
leaks into the chat UI (see `.claude/rules/ux-surface.md`).

## Intent & integration
The pipeline already centralizes every cross-cutting concern this needs — `pipeline.answer()`
orchestrates all four stages sequentially, already measures per-turn latency, threads a single
`CostLedger` through every stage, and emits the `audit` dict centrally. B-13 adds an
observability **provider seam** (mirroring the `llm.py` / `embeddings.py` adapters) and wraps
each stage from that one central place. **No agent signature changes; no agent files edited.**

- Per-stage token/cost comes from **ledger deltas**: snapshot `ledger.tokens` / `ledger.usd`
  before and after each stage — the delta is that stage's spend, because all stages share one
  ledger. No new accounting.
- The seam is **off by default and gated** like Azure/OpenRouter: the `LangfuseTracer` is chosen
  only when `observability_enabled` **and** keys are set; otherwise a `NoOpTracer`. Self-hosted /
  local Langfuse is $0; a hosted endpoint is only ever exercised on explicit enable.
- Export is **async / best-effort**: a tracing failure is caught and logged, never fails the turn
  (same posture as the audit write). When off, the seam is a true no-op — zero work on the path.
- `langfuse` is an **optional** dependency: the no-op path must import and run with the package
  absent (the `LangfuseTracer` imports it lazily inside its own branch).

## Module acceptance criteria
- [ ] With `observability_enabled=False` (the default), the pipeline behaves exactly as today:
      no tracing work on the path, no import of `langfuse`, byte-identical `AnswerResult` /
      `/query` payload, and the full existing suite still passes.
- [ ] With the flag on and keys set, a turn produces **one trace** with child spans for each
      executed stage in `tool_path` (route always; then `sql_agent` / `review_rag` / `docs_rag` /
      `compose` as applicable), each carrying `latency_ms` and the stage's token/cost delta.
- [ ] Trace/span metadata is **non-PII**: role, intent, tool_path, per-stage counts/timings/cost.
      The raw query text is **never** sent to the tracer.
- [ ] A tracer failure (export error, bad keys, provider down) is caught and logged and the turn
      still returns its normal answer — tracing is best-effort, never on the critical path.
- [ ] Nothing from the trace appears in the chat payload or the `audit` dict shape (no new keys
      that reach the UI). The observability plane is strictly operator-side.
- [ ] `ruff` / `black` clean on all changed/new files; $0 by default (flag off / self-hosted).

## Sub-modules (ordered, each build → verify → integrate)

### B13.1 Observability provider seam + config + deps
- Goal: a self-contained tracing adapter that is a no-op by default and only activates Langfuse
  when explicitly enabled and configured — with no effect on any caller until B13.2 wires it in.
- Acceptance criteria:
  - [ ] `backend/observability/tracing.py` defines a `Tracer` Protocol with: `start_trace(name, *,
        metadata) -> TraceHandle`, where the handle exposes a `span(name, *, metadata)` context
        manager (sync — it wraps `asyncio.to_thread` stages too) and an `end(metadata)` /`flush()`;
        plus a module-level `get_tracer()` (lru_cached like `get_settings`).
  - [ ] `NoOpTracer` is returned when `observability_enabled` is False **or** keys are missing; its
        trace/span handles do nothing and allocate nothing meaningful. `get_tracer()` never raises.
  - [ ] `LangfuseTracer` is returned only when `observability_enabled=True` **and** public+secret
        keys are set; it imports `langfuse` **lazily inside its own constructor/branch**, so the
        module imports cleanly with `langfuse` not installed. Construction failure (missing pkg,
        bad config) falls back to `NoOpTracer` with a logged warning — it never raises to a caller.
  - [ ] `backend/app/config.py` gains: `observability_enabled: bool = False`,
        `langfuse_host: str | None = None`, `langfuse_public_key: SecretStr | None = None`,
        `langfuse_secret_key: SecretStr | None = None`. All default off/None; no other setting changes.
  - [ ] `backend/.env.example` documents each new key (commented, off by default, with a one-line
        note that self-hosted Langfuse is $0 and hosted spends → log in `COST.md`).
  - [ ] `backend/pyproject.toml` adds `langfuse` under a new optional-dependencies group
        (e.g. `observability = ["langfuse"]`), **not** a hard runtime dependency.
  - [ ] Unit test: `get_tracer()` returns `NoOpTracer` when off (default) and when on-but-unkeyed;
        a no-op trace/span cycle runs without `langfuse` importable; non-PII is the only metadata
        the seam is designed to accept (assert the raw query is not among what B13.2 passes — see
        B13.2 test). `get_tracer.cache_clear()` is usable so tests can flip the flag.
- Build steps:
  1. `backend/observability/__init__.py`, `backend/observability/tracing.py`: `Tracer` Protocol,
     `NoOpTracer`, `LangfuseTracer` (lazy import), `get_tracer()`.
  2. Add the four settings to `config.py`; document them in `.env.example`.
  3. Add the optional `observability` dep group in `pyproject.toml`.
  4. `backend/tests/test_observability.py`: no-op selection + safe-fallback tests (no network).
- Files to touch: `backend/observability/__init__.py` (new), `backend/observability/tracing.py`
  (new), `backend/app/config.py`, `backend/.env.example`, `backend/pyproject.toml`,
  `backend/tests/test_observability.py` (new).
- Integration point: nothing calls the seam yet — this sub-module is inert until B13.2. Keeps the
  risky external-provider code isolated and independently testable.

### B13.2 Pipeline trace lifecycle + shutdown flush
- Goal: wrap the four stages in `pipeline.answer()` with spans from the seam, and flush the tracer
  on app shutdown — all behind the flag, with zero behaviour change when off.
- Acceptance criteria:
  - [ ] `pipeline.answer()` acquires `get_tracer()`, opens one trace per turn with non-PII metadata
        (role; filled with intent/tool_path as they become known), and wraps **each executed stage**
        — `route`, then `sql_agent` / `review_rag` / `docs_rag`, then `compose` — in a `span(...)`.
  - [ ] Each stage span records `latency_ms` and the **ledger delta** (`tokens`, `cost_usd`)
        measured as the before/after difference of `ledger.tokens` / `ledger.usd` around that stage.
  - [ ] The raw `query` / `retrieval_query` text is **never** passed to a span or trace; only
        role, intent, tool_path, and the per-stage numeric deltas/timings are.
  - [ ] All tracing is wrapped so any failure is caught + logged and the turn still returns normally
        (mirror the existing best-effort `record_audit` block). The `started`/latency and `audit`
        computation are unchanged; the returned `AnswerResult` and `/query` payload are identical to
        today when the flag is off **and** when it is on (the trace is side-channel only).
  - [ ] `backend/app/main.py` adds a shutdown handler (`@app.on_event("shutdown")` or lifespan) that
        calls the tracer's `flush()` so buffered spans are not lost. No request-handler logic changes;
        no new response fields; `/query` contract unchanged.
  - [ ] The span wrapping must not sit on the latency path when off: with `NoOpTracer`, the context
        managers are no-ops (no thread hops, no I/O).
- Build steps:
  1. In `pipeline.answer()`: `tracer = get_tracer()`; `trace = tracer.start_trace("query",
     metadata={"role": role})`. Around each stage call, snapshot the ledger, enter
     `trace.span("<stage>")`, run the stage, record the delta + timing in the span's exit metadata.
     After `compose`, set trace-level metadata (intent, tool_path) and `trace.end(...)`. Wrap the
     whole block so a tracer error degrades to the untraced path (log `warning`, continue).
  2. In `main.py`: a shutdown hook that calls `get_tracer().flush()` (guarded; never raises).
  3. Extend `backend/tests/test_observability.py` with a pipeline-level check using a **fake
     in-memory tracer** injected via the seam: assert one trace + a span per executed stage, that
     deltas are recorded, and that the raw query string appears in **no** span/trace metadata.
- Files to touch: `backend/agents/pipeline.py`, `backend/app/main.py`,
  `backend/tests/test_observability.py`.
- Integration point: consumes B13.1's `get_tracer()`; reads the existing `CostLedger`, `tool_path`,
  and stage calls already present in `answer()`. No agent file is edited; no audit-schema change.

## Out of scope / deferred
- **LLM-call-granular generation spans** (model name, prompt/completion token split) — would need
  one thin span inside `llm.py`. Deliberately left out to keep agents untouched; a clean later
  add-on if per-call granularity is ever wanted (noted in the ADR).
- No change to `audit_log`, the chat UI, or any agent signature. B-14 (audit admin view) is a
  separate item and must land after this (shared `main.py`).

## Testing notes (see `.claude/rules/testing.md`)
- Tests are **offline and deterministic** — no real Langfuse endpoint, no network. The Langfuse
  path is exercised via a fake/in-memory tracer injected at the seam, not a live export.
- Scoped tester run: `backend/tests/test_observability.py` + one real end-to-end `/query` smoke
  proving the flag-off path is byte-identical and never imports `langfuse`. Do **not** run the full
  backend suite (torch downloads hang) or `test_vector_store.py` (drops the real corpus) — see
  the session memory notes.
