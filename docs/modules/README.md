# Module notes and current implementation

The original module notes describe dated baseline deliveries. Read
[the current status](../answer-quality-status.md) before treating an older
“unchanged/out-of-scope/unstarted” paragraph as the current runtime contract.
Every changed path is mapped in [CHANGE_INVENTORY](../../context/CHANGE_INVENTORY.md).

| Area | Current remediation note | Spec |
|---|---|---|
| M7 baseline/evaluation | [Answer-quality baseline](M7_answer_quality_baseline.md) | [M7 appendix](../../.claude/specs/M7_evaluation.md) |
| M4/M5 selection/routing | [Stage2](M4_answer_quality_stage2.md) | [M4](../../.claude/specs/M4_retrieval_agents.md) / [M5](../../.claude/specs/M5_conversation_memory.md) |
| M2/M3/M4 evidence foundations | [Stage3](M3_answer_quality_stage3.md) | [Stage3 scope](../../.claude/specs/M3_answer_quality_stage3_proposal.md) |
| M4/M6/M8 source and presentation | [Practical workaround](M4_answer_quality_workaround.md) | [Workaround scope](../../.claude/specs/M4_answer_quality_stage4_workaround.md) |
| M4/M5/M8 natural conversations | [Conversational planning and live repair](M4_conversational_planning.md) | [Conversation scope](../../.claude/specs/M4_conversational_planning.md) |

Stage1/2 bounded work accepted; Stage3 isolated fixtures and later repairs are
implemented with quality review pending. Stage5 has not started. The original
M1–M8 DONE milestones do not imply a complete answer-quality pass; M9 remains TODO.

Original baseline notes remain in this directory for M1–M8, M8v2/v3/v4 and B13/B14.
They retain their original measurements; subsequent current notes supersede only
the affected implementation contracts. No serving migration is active.
