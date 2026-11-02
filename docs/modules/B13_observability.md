# B-13 — Observability plane (Langfuse tracing)

Date: 2026-11-02. Ran as a `/change` (not a module loop). Spec: `.claude/specs/B13_observability.md`.
ADR: `context/DECISIONS.md` (B-13, 2026-11-02). Cloud spend: $0 (flag off by default; self-hosted Langfuse is $0).

## What was built

An **operator-only** observability plane: span-level tracing of each turn through the pipeline
(router → SQL → retrieval → composer), with per-stage timing and token/cost attribution. It is a
provider seam mirroring the `llm.py` / `embeddings.py` adapters — **off by default, gated, and never
on the per-query latency path**. Nothing from it reaches the chat UI or changes the `audit` dict or
`/query` payload (see `.claude/rules/ux-surface.md`). Built as **Option A**: all spans are emitted
centrally from `pipeline.answer()`; **no agent file was edited**.

| Sub-module | Delivered | Key files |
|---|---|---|
| B13.1 Provider seam + config + optional dep | `Tracer` Protocol + `NoOpTracer` (default) + `LangfuseTracer` (lazy `langfuse` import inside its own branch — module imports fine with the package absent). `get_tracer()` (lru_cached) returns `NoOpTracer` unless `observability_enabled` **and** both keys are set, and never raises — a construction failure logs a warning (exception type only) and falls back to no-op. `_safe()` strips text keys + non-scalars so the seam is non-PII by design. Four settings added, all off/None | `backend/observability/tracing.py` (new), `__init__.py` (new), `app/config.py`, `.env.example`, `pyproject.toml` (optional `observability` group), `tests/test_observability.py` (new, 6) |
| B13.2 Pipeline trace lifecycle + shutdown flush | `pipeline.answer()` opens one trace/turn (`metadata={"role": role}`) and wraps each executed stage in a `_stage(...)` context manager that snapshots `ledger.tokens`/`.usd` + a timer before the stage and records the delta + `latency_ms` via `span.update(...)` in a `finally`. Spans: `route`, then whichever of `sql_agent`/`review_rag`/`docs_rag` run, then `compose`. `_end_trace` sets intent + tool_path. Every tracer call is `try/except`-wrapped (logs exception type only) so tracing never fails or alters the turn. `main.py` gains a `lifespan` shutdown hook that flushes the tracer in a thread, guarded | `backend/agents/pipeline.py`, `backend/app/main.py`, `tests/test_observability.py` (extended, +2 → 8) |

### Settings keys added

| Key | Default | Purpose |
|---|---|---|
| `observability_enabled` | `false` | Master switch; off → `NoOpTracer`, zero work on the path |
| `langfuse_host` | `None` | Langfuse endpoint (self-hosted = $0; hosted spends → log in `COST.md`) |
| `langfuse_public_key` | `None` (SecretStr) | Langfuse public key |
| `langfuse_secret_key` | `None` (SecretStr) | Langfuse secret key |

All documented in `.env.example`. `langfuse` is an **optional** dependency (`pyproject.toml`
`[project.optional-dependencies] observability`), never a hard runtime dep.

## Key decisions

| Decision | Why | Rejected alternative |
|---|---|---|
| Central span seam in `pipeline.answer()`, agents untouched (Option A) | The pipeline already orchestrates every stage, measures latency, and threads one `CostLedger` — per-stage token/cost falls out as a ledger delta with zero agent edits; smallest blast radius; "off = true no-op" trivial to guarantee at one site | Per-agent spans (the backlog's literal file list) — threads the provider through 5 agent files for the same value; harder no-op guarantee |
| Per-stage token/cost = ledger delta (snapshot before/after each stage) | All stages share one ledger, so the delta across a stage *is* that stage's spend — no new accounting | Instrumenting each LLM call inside `llm.py` |
| Non-PII metadata only (role, intent, tool_path, numeric deltas); raw query never passed to a span | Operator plane must not become a PII sink; `_safe()` is a second guard that drops text keys by name | Sending the query text for richer traces |
| Best-effort, off the latency path (lazy import, no-op default, async flush, all calls `try/except`) | Tracing an answer must never slow or fail the answer — same posture as the best-effort audit write | A hard Langfuse dependency / synchronous export on the request path |

## Deferred / where we stopped

- **LLM-call-granular generation spans** (model name, prompt/completion token split) — would need one
  thin span inside `llm.py`. Left out to keep agents untouched; a clean later add-on.
- **Live Langfuse export unverified.** `langfuse` isn't installed and the flag is off, so only the
  `NoOpTracer` and fake-tracer paths were exercised. The `LangfuseTracer` assumes the Langfuse v3
  client (`start_span`/`update`/`end`/`flush`) — verify against the installed version before enabling.
- **No committed test for the `lifespan` flush** — confirmed once via an ad-hoc scratchpad script
  (flush raising → logged, not raised). Acceptable for a $0 best-effort shutdown hook.

## Tests

Offline/deterministic, no network. `tests/test_observability.py` → **8 passed**: no-op selection
(off / enabled-unkeyed / keyed-but-langfuse-absent fallback), a full no-op trace/span/update/end/flush
cycle, `_safe()` stripping text + non-scalars, a pipeline turn producing exactly one trace + a span per
executed stage with recorded deltas and **the raw query absent from all trace/span metadata**, and a
turn surviving a `start_trace` that raises. Flag-off smoke: `tests/test_pipeline.py -k "not seeded and
not live"` → **3 passed** (drives `answer()`/`/query` under the default `NoOpTracer`). `ruff`/`black`
clean on all changed/new files.
