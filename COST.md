# COST.md

Cloud spend log. Every action that spends money is logged here; nothing is
provisioned or run without explicit human go-ahead. Runtime cap lives in
`Settings` (`max_cost_usd`, `max_tokens_per_query`) and is enforced by `CostLedger`.

| Date       | Module | Service                  | Estimated (USD) | Actual (USD) |
|------------|--------|--------------------------|-----------------|--------------|
| 2026-10-27 | M1     | none (IaC stubs only)    | 0.00            | 0.00         |
| 2026-10-27 | M2     | none (Spark local mode)  | 0.00            | 0.00         |
| 2026-10-27 | M3     | none (local embed+pgvec) | 0.00            | 0.00         |
| 2026-10-27 | M4     | none (free LLM/retrieval)| 0.00            | 0.00         |
| 2026-10-27 | M5     | none (determ. summariser)| 0.00            | 0.00         |
| 2026-10-27 | M6     | none (local policy/audit)| 0.00            | 0.00         |
| 2026-10-27 | M7     | none (free eval + CI gate)| 0.00           | 0.00         |
| 2026-10-28 | M8     | none (inert deploy, free) | 0.00            | 0.00         |
| 2026-10-29 | M8v3   | none (inert deploy, free) | 0.00            | 0.00         |
