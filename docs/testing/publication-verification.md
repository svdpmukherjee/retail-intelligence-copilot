# Pre-publication verification — 2026-11-03

Scope: all uncommitted remediation work since `ec0ef26`, plus handoff cleanup.
This is a publication check, not full answer-quality acceptance or a new hosted run.

| Check | Outcome |
|---|---|
| Combined inspected hermetic suites | 177 passed; command in unit-testing.md; no shared conftest, serving DB or hosted model |
| Whole backend Ruff | Pass |
| Whole backend Black | Pass,107files; backend/pyproject.toml config explicitly selected |
| Changed Gold/Spark fixture Python format/lint | Pass; no Spark job started |
| Frontend answer-quality harness | Pass |
| Frontend TypeScript + Vite production build | Pass,64modules |
| Whitespace, local doc links, changed-file coverage, frozen snapshot hashes | Checked before commit |
| Six baseline formatting files | AST identical before/after; isolated formatting commit |
| Full DB-backed pytest / docs-only CI eval / new hosted campaign | Not run in this audit |

The initial broader run found A12's no-model replacement-metric loop and the
Stage3 partial-state test's old ambiguous prompt. Resolution:

- A concrete most-reviewed/best-rated replacement does not inherit the unavailable
  revenue/sales measure; requested category is retained, explicit new category wins.
  The unavailable-measure guard stays active for actual new sales/revenue requests.
- Stage3 supplies explicit lowest-average/minimum2/show1 criteria; original
  partial-state/source-limit assertions remain unchanged.
- That explicit prompt exposed an imperative decomposition bug: “and show1” was
  treated as a new query. Numeric display modifiers stay with their original task;
  named independent “and show the five cheapest…” companions still decompose.
- No synthetic result snapshots or assertion thresholds were rewritten to get PASS.

Formatting-only paths (no AST/behavior changes): backend/app/main.py,
backend/agents/llm.py, backend/observability/tracing.py, backend/memory/store.py,
backend/tests/test_audit_read.py, backend/tests/test_pipeline_memory.py.
The first multi-project formatter invocation selected a common-root default;
verification was rerun with explicit backend config /data line-length100 to avoid
misreporting unrelated formatting changes. Only the six baseline files were normalized.

The earlier138-test result and71real browser turns/27queries remain historical
measurements, not counts to add to this run. Live latest-outcome25checks, SQL
independent truths, read-only corpus preservation and remaining excerpt fallbacks
are summarized in [current status](../answer-quality-status.md). Local raw evidence
is not committed. Citation syntax and these tests do not prove general entailment.

Documentation, schema/migration boundary and all path mappings were reconciled
against the actual final diff. README, agent entry points, context, specs, module
notes, test instructions, cost ledger and repo-evolution refer to the current
handoff. Publication does not authorize a merge/deployment/backfill or accept quality.
New hosted/embedding/cloud cost for this audit: $0.
