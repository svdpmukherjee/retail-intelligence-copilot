# Change inventory since ec0ef26

Baseline: `ec0ef266ca2d1bfa4094e19a9dbfaa1dd4006738`. Branch: `plan/answer-quality-remediation`.
Updated 2026-11-03. Every changed/new source, test, configuration, spec and document
path is listed below with a documentation owner. This is the publication inventory,
not evidence that every feature or answer is accepted. See [current status](../docs/answer-quality-status.md).

**123 paths**, including this inventory. Historical synthetic snapshots are frozen;
live transcripts/corpus/secrets/browser profiles remain outside Git. Commit references
are in CURRENT_TASK/WORKLOG; the inventory is independent of its own commit hash.

## Agent entry and current handoff

Owner: [docs/answer-quality-status.md](../docs/answer-quality-status.md). Documentation-only current snapshot; historical notes retained.

- [AGENTS.md](../AGENTS.md)
- [CLAUDE.md](../CLAUDE.md)
- [COST.md](../COST.md)
- [README.md](../README.md)
- [context/CHANGE_INVENTORY.md](../context/CHANGE_INVENTORY.md)
- [context/CURRENT_TASK.md](../context/CURRENT_TASK.md)
- [context/DECISIONS.md](../context/DECISIONS.md)
- [context/PROJECT.md](../context/PROJECT.md)
- [context/RESUME_NEXT_SESSION.md](../context/RESUME_NEXT_SESSION.md)
- [context/WORKLOG.md](../context/WORKLOG.md)

## Baseline backend formatting

Owner: [docs/testing/publication-verification.md](../docs/testing/publication-verification.md). AST-equivalent formatting, separate commit.

- [backend/agents/llm.py](../backend/agents/llm.py)
- [backend/app/main.py](../backend/app/main.py)
- [backend/memory/store.py](../backend/memory/store.py)
- [backend/observability/tracing.py](../backend/observability/tracing.py)
- [backend/tests/test_audit_read.py](../backend/tests/test_audit_read.py)
- [backend/tests/test_pipeline_memory.py](../backend/tests/test_pipeline_memory.py)

## M4 planning / SQL / composition

Owner: [docs/modules/M4_conversational_planning.md](../docs/modules/M4_conversational_planning.md). Active runtime; bounded quality review pending.

- [backend/agents/_rag.py](../backend/agents/_rag.py)
- [backend/agents/answer_evidence.py](../backend/agents/answer_evidence.py)
- [backend/agents/catalogue.py](../backend/agents/catalogue.py)
- [backend/agents/composer.py](../backend/agents/composer.py)
- [backend/agents/conversation.py](../backend/agents/conversation.py)
- [backend/agents/model_policy.py](../backend/agents/model_policy.py)
- [backend/agents/pipeline.py](../backend/agents/pipeline.py)
- [backend/agents/product_criteria.py](../backend/agents/product_criteria.py)
- [backend/agents/query_plan.py](../backend/agents/query_plan.py)
- [backend/agents/router.py](../backend/agents/router.py)
- [backend/agents/sql_agent.py](../backend/agents/sql_agent.py)
- [backend/agents/suggestions.py](../backend/agents/suggestions.py)

## M3 evidence and M4 source retrieval

Owner: [docs/modules/M3_answer_quality_stage3.md](../docs/modules/M3_answer_quality_stage3.md). Legacy/source-first serving plus isolated opt-in fixture foundations; no corpus migration.

- [backend/retrieval/chunking.py](../backend/retrieval/chunking.py)
- [backend/retrieval/embeddings.py](../backend/retrieval/embeddings.py)
- [backend/retrieval/evidence_bundle.py](../backend/retrieval/evidence_bundle.py)
- [backend/retrieval/hybrid.py](../backend/retrieval/hybrid.py)
- [backend/retrieval/index_docs.py](../backend/retrieval/index_docs.py)
- [backend/retrieval/index_reviews.py](../backend/retrieval/index_reviews.py)
- [backend/retrieval/normalization.py](../backend/retrieval/normalization.py)
- [backend/retrieval/provenance.py](../backend/retrieval/provenance.py)
- [backend/retrieval/schema.py](../backend/retrieval/schema.py)
- [backend/retrieval/selection.py](../backend/retrieval/selection.py)
- [backend/retrieval/source_reviews.py](../backend/retrieval/source_reviews.py)
- [backend/retrieval/sufficiency.py](../backend/retrieval/sufficiency.py)
- [backend/retrieval/vector_store.py](../backend/retrieval/vector_store.py)

## M5 memory payload

Owner: [docs/modules/M5_conversation_memory.md](../docs/modules/M5_conversation_memory.md). Additive JSON active/clarification/suggestion state; no DDL.

- [backend/memory/manager.py](../backend/memory/manager.py)

## M6 citation checks

Owner: [docs/modules/M6_governance.md](../docs/modules/M6_governance.md). Grouped references/retention; authorization policy unchanged.

- [backend/governance/grounding.py](../backend/governance/grounding.py)

## M2 forward Gold

Owner: [docs/modules/M3_answer_quality_stage3.md](../docs/modules/M3_answer_quality_stage3.md). Forward metadata/identity code, synthetic fixture run only; no serving ETL.

- [data/etl/gold.py](../data/etl/gold.py)
- [data/tests/test_gold_stage3.py](../data/tests/test_gold_stage3.py)

## M7 harness / fixtures / frozen snapshots

Owner: [docs/testing/acceptance/README.md](../docs/testing/acceptance/README.md). Synthetic contract artifacts, guarded live runner, independent coverage; not a full quality pass.

- [backend/eval/evidence_coverage.py](../backend/eval/evidence_coverage.py)
- [backend/eval/ground_truth/quality_cases.json](../backend/eval/ground_truth/quality_cases.json)
- [backend/eval/ground_truth/quality_fixture.json](../backend/eval/ground_truth/quality_fixture.json)
- [backend/eval/hosted_quality_probe.py](../backend/eval/hosted_quality_probe.py)
- [backend/eval/quality_baseline.py](../backend/eval/quality_baseline.py)
- [backend/eval/quality_fixture.py](../backend/eval/quality_fixture.py)
- [backend/eval/stage3_evidence_smoke.py](../backend/eval/stage3_evidence_smoke.py)
- [docs/testing/acceptance/README.md](../docs/testing/acceptance/README.md)
- [docs/testing/acceptance/evidence-stage3.json](../docs/testing/acceptance/evidence-stage3.json)
- [docs/testing/acceptance/evidence-stage3.md](../docs/testing/acceptance/evidence-stage3.md)
- [docs/testing/acceptance/quality-baseline.json](../docs/testing/acceptance/quality-baseline.json)
- [docs/testing/acceptance/quality-baseline.md](../docs/testing/acceptance/quality-baseline.md)
- [docs/testing/acceptance/quality-stage2.json](../docs/testing/acceptance/quality-stage2.json)
- [docs/testing/acceptance/quality-stage2.md](../docs/testing/acceptance/quality-stage2.md)
- [docs/testing/acceptance/snapshot-checksums.json](../docs/testing/acceptance/snapshot-checksums.json)

## Backend configuration

Owner: [docs/answer-quality-status.md](../docs/answer-quality-status.md). Documented non-secret defaults and gated/optional fixture paths.

- [backend/.env.example](../backend/.env.example)
- [backend/app/config.py](../backend/app/config.py)

## Backend regression tests

Owner: [docs/testing/unit-testing.md](../docs/testing/unit-testing.md). Inspected hermetic checks; DB-backed suites not run here.

- [backend/tests/test_answer_truthfulness.py](../backend/tests/test_answer_truthfulness.py)
- [backend/tests/test_combined_questions.py](../backend/tests/test_combined_questions.py)
- [backend/tests/test_composer.py](../backend/tests/test_composer.py)
- [backend/tests/test_conversation_planning.py](../backend/tests/test_conversation_planning.py)
- [backend/tests/test_evidence_coverage.py](../backend/tests/test_evidence_coverage.py)
- [backend/tests/test_hosted_quality_probe.py](../backend/tests/test_hosted_quality_probe.py)
- [backend/tests/test_model_policy.py](../backend/tests/test_model_policy.py)
- [backend/tests/test_natural_conversation.py](../backend/tests/test_natural_conversation.py)
- [backend/tests/test_quality_baseline.py](../backend/tests/test_quality_baseline.py)
- [backend/tests/test_source_review_workaround.py](../backend/tests/test_source_review_workaround.py)
- [backend/tests/test_stage2_quality.py](../backend/tests/test_stage2_quality.py)
- [backend/tests/test_stage3_evidence.py](../backend/tests/test_stage3_evidence.py)

## M8 frontend and rendering checks

Owner: [docs/modules/M4_answer_quality_workaround.md](../docs/modules/M4_answer_quality_workaround.md). Active live/history safe rendering, truthful result states and contextual suggestions.

- [frontend/package.json](../frontend/package.json)
- [frontend/src/App.css](../frontend/src/App.css)
- [frontend/src/App.tsx](../frontend/src/App.tsx)
- [frontend/src/answer.ts](../frontend/src/answer.ts)
- [frontend/src/api/types.ts](../frontend/src/api/types.ts)
- [frontend/src/components/AnswerDocument.tsx](../frontend/src/components/AnswerDocument.tsx)
- [frontend/src/components/AssistantTurn.tsx](../frontend/src/components/AssistantTurn.tsx)
- [frontend/src/components/EvidencePanel.tsx](../frontend/src/components/EvidencePanel.tsx)
- [frontend/src/components/QuestionSuggestions.tsx](../frontend/src/components/QuestionSuggestions.tsx)
- [frontend/src/components/StackedTurns.tsx](../frontend/src/components/StackedTurns.tsx)
- [frontend/src/components/shapes/DefaultShape.tsx](../frontend/src/components/shapes/DefaultShape.tsx)
- [frontend/src/components/shapes/ExecutiveShape.tsx](../frontend/src/components/shapes/ExecutiveShape.tsx)
- [frontend/src/components/shapes/MarketingShape.tsx](../frontend/src/components/shapes/MarketingShape.tsx)
- [frontend/src/components/shapes/SqlData.tsx](../frontend/src/components/shapes/SqlData.tsx)
- [frontend/src/components/shapes/SqlTable.tsx](../frontend/src/components/shapes/SqlTable.tsx)
- [frontend/src/components/shapes/SupportShape.tsx](../frontend/src/components/shapes/SupportShape.tsx)
- [frontend/src/components/shapes/Trend.tsx](../frontend/src/components/shapes/Trend.tsx)
- [frontend/src/panelState.ts](../frontend/src/panelState.ts)
- [frontend/tests/answer-quality.mjs](../frontend/tests/answer-quality.mjs)

## Specification appendices

Owner: [docs/answer-quality-status.md](../docs/answer-quality-status.md). Authorized localized contract updates; historical scope statements superseded where noted.

- [.claude/specs/M2_data_ingestion_etl.md](../.claude/specs/M2_data_ingestion_etl.md)
- [.claude/specs/M3_answer_quality_stage3_proposal.md](../.claude/specs/M3_answer_quality_stage3_proposal.md)
- [.claude/specs/M3_indexing.md](../.claude/specs/M3_indexing.md)
- [.claude/specs/M4_answer_quality_stage4_workaround.md](../.claude/specs/M4_answer_quality_stage4_workaround.md)
- [.claude/specs/M4_conversational_planning.md](../.claude/specs/M4_conversational_planning.md)
- [.claude/specs/M4_retrieval_agents.md](../.claude/specs/M4_retrieval_agents.md)
- [.claude/specs/M5_conversation_memory.md](../.claude/specs/M5_conversation_memory.md)
- [.claude/specs/M6_governance.md](../.claude/specs/M6_governance.md)
- [.claude/specs/M7_evaluation.md](../.claude/specs/M7_evaluation.md)
- [.claude/specs/M8v4_serving_ui.md](../.claude/specs/M8v4_serving_ui.md)

## Architecture, module and verification notes

Owner: [docs/answer-quality-status.md](../docs/answer-quality-status.md). Documentation-only cross-links/status/history/test procedures.

- [docs/GUIDE.md](../docs/GUIDE.md)
- [docs/answer-quality-status.md](../docs/answer-quality-status.md)
- [docs/model-comparison.md](../docs/model-comparison.md)
- [docs/modules/M2_data_ingestion_etl.md](../docs/modules/M2_data_ingestion_etl.md)
- [docs/modules/M3_answer_quality_stage3.md](../docs/modules/M3_answer_quality_stage3.md)
- [docs/modules/M3_indexing.md](../docs/modules/M3_indexing.md)
- [docs/modules/M4_answer_quality_stage2.md](../docs/modules/M4_answer_quality_stage2.md)
- [docs/modules/M4_answer_quality_workaround.md](../docs/modules/M4_answer_quality_workaround.md)
- [docs/modules/M4_conversational_planning.md](../docs/modules/M4_conversational_planning.md)
- [docs/modules/M4_retrieval_agents.md](../docs/modules/M4_retrieval_agents.md)
- [docs/modules/M5_conversation_memory.md](../docs/modules/M5_conversation_memory.md)
- [docs/modules/M6_governance.md](../docs/modules/M6_governance.md)
- [docs/modules/M7_answer_quality_baseline.md](../docs/modules/M7_answer_quality_baseline.md)
- [docs/modules/M7_evaluation.md](../docs/modules/M7_evaluation.md)
- [docs/modules/M8v4_serving_ui.md](../docs/modules/M8v4_serving_ui.md)
- [docs/modules/README.md](../docs/modules/README.md)
- [docs/repo-evolution.md](../docs/repo-evolution.md)
- [docs/testing/answer-quality-change-proposal.md](../docs/testing/answer-quality-change-proposal.md)
- [docs/testing/publication-verification.md](../docs/testing/publication-verification.md)
- [docs/testing/unit-testing.md](../docs/testing/unit-testing.md)
