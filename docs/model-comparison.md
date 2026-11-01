# Model comparison study (B-8)

> **Real gated run** on 2026-11-01 via provider `openrouter`.

## Results

| Model | Tier | Family | Faithfulness | Grounded-path rate | Citation validity | Routing accuracy | p50 ms | p95 ms | $/query | License | Portability |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma-3-4b | small | google | 1.00 | 1.00 | 1.00 | 0.75 | 2670 | 5473 | $0.000037 | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) |
| ministral-3-3b-2512 | small | mistral | 0.95 | 1.00 | 1.00 | 0.75 | 2028 | 3176 | $0.000064 | Apache-2.0 | open-weight, OSI, self-host/on-prem |
| gemma-3-12b | medium | google | 1.00 | 1.00 | 1.00 | 0.88 | 3036 | 4622 | $0.000048 | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) |
| ministral-3-14b-2512 | medium | mistral | 0.95 | 1.00 | 1.00 | 0.88 | 2131 | 3710 | $0.000135 | Apache-2.0 | open-weight, OSI, self-host/on-prem |
| gemma-3-27b | large | google | 0.95 | 1.00 | 1.00 | 1.00 | 3143 | 6438 | $0.000075 | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) |
| mistral-small-3.1-24b | large | mistral | 0.95 | 1.00 | 1.00 | 0.88 | 2020 | 3727 | $0.000177 | Apache-2.0 | open-weight, OSI, self-host/on-prem |

## Descriptive SQL (descriptive, not gated)

Count of SQL questions whose emitted SQL passed the read-only SELECT guard and ran on the scoped Gold table. Reported for information; no threshold applies.

| Model | Runnable / total |
|---|---|
| gemma-3-4b | 4 / 4 |
| ministral-3-3b-2512 | 4 / 4 |
| gemma-3-12b | 4 / 4 |
| ministral-3-14b-2512 | 3 / 4 |
| gemma-3-27b | 4 / 4 |
| mistral-small-3.1-24b | 4 / 4 |

## Methodology

- **One axis varied: the generation model.** Embeddings, retrieval, SQL engine, prompts and judge are held fixed.
- **Judge:** deterministic and $0 (model-agnostic), which avoids judge-model bias.
- **Latency** reflects the B-11 index-hitting (HNSW) serving path.
- **$/query** = token usage x the per-model price in `models.json`. It is an estimate: the audit holds one worst-case total (prompt estimate + `max_tokens` reservation), split into input (total minus the reservation) and output (estimated answer tokens).
- Routing accuracy and SQL runnability are reported, not gated.

## Models & pricing

| Model | Slug | License | Portability | $/1M in | $/1M out | Price confidence |
|---|---|---|---|---|---|---|
| gemma-3-4b | `google/gemma-3-4b-it` | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) | 0.05 | 0.1 | confirmed (OpenRouter API, 2026-11-01) |
| ministral-3-3b-2512 | `mistralai/ministral-3b-2512` | Apache-2.0 | open-weight, OSI, self-host/on-prem | 0.1 | 0.1 | confirmed (OpenRouter API, 2026-11-01) |
| gemma-3-12b | `google/gemma-3-12b-it` | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) | 0.05 | 0.15 | confirmed (OpenRouter API, 2026-11-01) |
| ministral-3-14b-2512 | `mistralai/ministral-14b-2512` | Apache-2.0 | open-weight, OSI, self-host/on-prem | 0.2 | 0.2 | confirmed (OpenRouter API, 2026-11-01) |
| gemma-3-27b | `google/gemma-3-27b-it` | Gemma Terms of Use | open-weight, commercial-with-conditions (not OSI) | 0.08 | 0.35 | confirmed (OpenRouter API, 2026-11-01) |
| mistral-small-3.1-24b | `mistralai/mistral-small-3.1-24b-instruct` | Apache-2.0 | open-weight, OSI, self-host/on-prem | 0.351 | 0.555 | confirmed (OpenRouter API, 2026-11-01) |

Prices are provisional; re-confirm live against OpenRouter before the paid run. Source notes: `backend/eval/ground_truth/models.README.md`.

The large Mistral (Mistral Small 3.1 24B, 2503) is a different vintage than its 2512 small and medium siblings, so the Mistral family trend is not a clean size sweep.

## Golden sets

Committed under `backend/eval/ground_truth/`: `answers.json`, `study_routing.json`, `study_sql.json`.
