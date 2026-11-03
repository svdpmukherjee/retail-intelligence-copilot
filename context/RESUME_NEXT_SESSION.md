# Resume — current handoff (2026-11-03)

This supersedes the 2026-11-01 “clean main / no task” handoff. Read AGENTS.md and
CLAUDE.md, then PROJECT.md, CURRENT_TASK.md, recent WORKLOG/DECISIONS entries and
[the consolidated status](../docs/answer-quality-status.md).

1. Inspect `git status --short`, branch and recent log. Work is published on
   `plan/answer-quality-remediation`, based on GitHub `ec0ef26`; check the actual
   repository for the latest hashes/tracking state rather than assuming main.
2. Use [CHANGE_INVENTORY.md](CHANGE_INVENTORY.md) to locate each changed subsystem,
   its spec, module note and tests. M1–M8 DONE refers to the historical baseline;
   remediation review is a separate status. M9 remains TODO.
3. Stage 1/2 accepted; Stage 3 isolated fixtures and later workaround/conversational
   repairs implemented, quality acceptance pending. Publishing does not accept
   quality, enable a serving migration or authorize a new model/cost campaign.
4. No corpus rebuild is needed to inspect/test the code. The recorded serving
   corpus is 225,000 review +79doc chunks; SQL has911,308 reviews/645,448 products,
   whereas indexed reviews cover191,007 products. These are dated local findings,
   not a guarantee that a fresh clone contains the corpus.
5. Stage 3 `EVIDENCE_BUNDLE_PATH` is optional and was unset in live checks. Do not
   activate it or run Gold ETL/indexers against serving data. Source-first selected
   product reviews use bounded read-only Silver lookup with aggregate checks.
6. Test safely using [unit-testing.md](../docs/testing/unit-testing.md). Shared
   conftest creates a `_test` DB and DB suites may DROP tables; `--noconftest` is
   only for the named inspected hermetic suites. Do not run eval/index setup on the
   serving DB to get a green report. CI owns its isolated database.
7. Synthetic Stage1/2/3 snapshots in docs/testing/acceptance are frozen. Write new
   observations elsewhere. Local `/private/tmp/ric-*` evidence may disappear and
   is not part of Git; durable summaries and limitations are committed.
8. Some hosted Pet/policy answers intentionally degrade to excerpts. Syntax checks,
   retrieval scores and larger-model selection are not proof of factual support.
   Do not say the broad answer-quality gate passed or start Stage5 unasked.

Provider configuration lives in ignored backend/.env; never print or commit it.
Historical free/OpenRouter settings are observations, not an instruction to toggle
them. Current examples/defaults live in backend/.env.example. No secrets, raw data,
model cache, live transcripts or browser profiles belong in Git.

The latest user authorized documentation, commits and pushing this branch only.
No deployment/main merge, corpus/schema migration, ETL/reindex/download or arbitrary
new paid work is authorized. Prior temporary services are stopped. Do not execute
old cloud teardown/setup snippets from historical handoff notes.
