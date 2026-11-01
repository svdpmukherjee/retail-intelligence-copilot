# Model comparison study (B-8)

> **DRY-RUN (placeholder numbers).** Produced at $0 by the canned `DryRunLLM`; these figures show the format only and say nothing about the models. Generated 2026-11-01.

## Results

| Model | Tier | Family | Faithfulness | Grounded-path rate | Citation validity | Routing accuracy | p50 ms | p95 ms | $/query | License | Portability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma-3-4b | small | google | 0.50 | 1.00 | 1.00 | 0.25 | 1223 | 3508 | $0.000009 | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) |
| ministral-3-3b-2512 | small | mistral | 0.50 | 1.00 | 1.00 | 0.25 | 1210 | 1305 | $0.000044 | Apache-2.0 | open-weight, OSI, self-host/on-prem |
| gemma-3-12b | medium | google | 0.50 | 1.00 | 1.00 | 0.25 | 1202 | 1244 | $0.000023 | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) |
| ministral-3-14b-2512 | medium | mistral | 0.50 | 1.00 | 1.00 | 0.25 | 1231 | 1356 | $0.000066 | Apache-2.0 | open-weight, OSI, self-host/on-prem |
| gemma-3-27b | large | google | 0.50 | 1.00 | 1.00 | 0.25 | 1223 | 197132 | $0.000036 | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) |
| mistral-small-3.1-24b | large | mistral | 0.50 | 1.00 | 1.00 | 0.25 | 1226 | 1320 | $0.000157 | Apache-2.0 | open-weight, OSI, self-host/on-prem |

## Descriptive SQL (descriptive, not gated)

Count of SQL questions whose emitted SQL passed the read-only SELECT guard and ran on the scoped Gold table. Reported for information; no threshold applies.

| Model | Runnable / total |
|---|---|
| gemma-3-4b | 0 / 4 |
| ministral-3-3b-2512 | 0 / 4 |
| gemma-3-12b | 0 / 4 |
| ministral-3-14b-2512 | 0 / 4 |
| gemma-3-27b | 0 / 4 |
| mistral-small-3.1-24b | 0 / 4 |

## Methodology

- **One axis varied: the generation model.** Embeddings, retrieval, SQL engine, prompts and judge are held fixed.
- **Judge:** deterministic and $0 (model-agnostic), which avoids judge-model bias.
- **Latency** reflects the B-11 index-hitting (HNSW) serving path.
- **$/query** = token usage x the per-model price in `models.json`. It is an estimate: the audit holds one worst-case total (prompt estimate + `max_tokens` reservation), split into input (total minus the reservation) and output (estimated answer tokens).
- Routing accuracy and SQL runnability are reported, not gated.

## Models & pricing

| Model | Slug | License | Portability | $/1M in | $/1M out | Price confidence |
|---|---|---|---|---|---|---|
| gemma-3-4b | `google/gemma-3-4b-it` | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) | 0.02 | 0.04 | low (unconfirmed) |
| ministral-3-3b-2512 | `mistralai/ministral-3-3b-instruct-2512` | Apache-2.0 | open-weight, OSI, self-host/on-prem | 0.1 | 0.1 | low (unconfirmed) |
| gemma-3-12b | `google/gemma-3-12b-it` | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) | 0.05 | 0.15 | medium |
| ministral-3-14b-2512 | `mistralai/ministral-3-14b-instruct-2512` | Apache-2.0 | open-weight, OSI, self-host/on-prem | 0.15 | 0.15 | low (unconfirmed) |
| gemma-3-27b | `google/gemma-3-27b-it` | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) | 0.08 | 0.16 | medium |
| mistral-small-3.1-24b | `mistralai/mistral-small-3.1-24b-instruct` | Apache-2.0 | open-weight, OSI, self-host/on-prem | 0.35 | 0.56 | medium |

Prices are provisional; re-confirm live against OpenRouter before the paid run. Source notes: `backend/eval/ground_truth/models.README.md`.

The large Mistral (Mistral Small 3.1 24B, 2503) is a different vintage than its 2512 small and medium siblings, so the Mistral family trend is not a clean size sweep.

## Golden sets

Committed under `backend/eval/ground_truth/`: `answers.json`, `study_routing.json`, `study_sql.json`.
