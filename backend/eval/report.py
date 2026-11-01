"""Model-study report renderer and up-front spend estimate (pure: no network, no DB)."""

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from agents.composer import SYSTEM_PROMPT as ANSWER_PROMPT
from agents.llm import estimate_tokens
from agents.router import SYSTEM_PROMPT as ROUTER_PROMPT
from agents.sql_agent import SYSTEM_PROMPT as SQL_PROMPT
from app.config import get_settings
from eval.answer_eval import GROUND_TRUTH
from eval.study_cost import dollars_for, load_models

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "docs" / "model-comparison.md"
COST_PATH = REPO_ROOT / "COST.md"
ROUTING_SET = GROUND_TRUTH.with_name("study_routing.json")
SQL_SET = GROUND_TRUTH.with_name("study_sql.json")
TIER_ORDER = {"small": 0, "medium": 1, "large": 2}
# Prompt text unseen before a run: retrieved sources in the answer prompt, Gold columns in the SQL
# prompt. Fixed allowances keep the estimate a conservative round number.
ANSWER_CONTEXT_TOKENS = 1500
SQL_CONTEXT_TOKENS = 300
ROUTER_MAX_TOKENS = 100  # mirrors agents.router's complete(..., max_tokens=100)


def _count(path: Path) -> int:
    return len(json.loads(path.read_text(encoding="utf-8")))


def _call_cost(model: dict, system: str, questions: list[str], context: int, limit: int) -> float:
    """Worst case per OpenRouterLLM.complete: prompt estimate in, max_tokens reserved out."""
    return sum(dollars_for(model, estimate_tokens(system, q) + context, limit) for q in questions)


def estimate_spend(models: list[dict] | None = None) -> dict:
    """Worst-case spend before any paid call: {"per_model": {id: usd}, "total": usd, "calls": n}."""
    models = models if models is not None else load_models()
    max_tokens = get_settings().llm_max_tokens
    answers = [c["question"] for c in json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))]
    routing = [c["question"] for c in json.loads(ROUTING_SET.read_text(encoding="utf-8"))]
    sql = [c["question"] for c in json.loads(SQL_SET.read_text(encoding="utf-8"))]
    per_model = {
        m["id"]: _call_cost(m, ANSWER_PROMPT, answers, ANSWER_CONTEXT_TOKENS, max_tokens)
        + _call_cost(m, ROUTER_PROMPT, routing, 0, ROUTER_MAX_TOKENS)
        + _call_cost(m, SQL_PROMPT, sql, SQL_CONTEXT_TOKENS, max_tokens)
        for m in models
    }
    return {
        "per_model": per_model,
        "total": sum(per_model.values()),
        "calls": (len(answers) + len(routing) + len(sql)) * len(models),
    }


def _sorted(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (TIER_ORDER.get(r["tier"], 99), r["family"], r["id"]))


def _table(rows: list[dict]) -> list[str]:
    head = (
        "| Model | Tier | Family | Faithfulness | Grounded-path rate | Citation validity "
        "| Routing accuracy | p50 ms | p95 ms | $/query | License | Portability |"
    )
    lines = [head, "|" + "---|" * 12]
    for r in _sorted(rows):
        lines.append(
            f"| {r['id']} | {r['tier']} | {r['family']} | {r['faithfulness']:.2f} "
            f"| {r['grounded_path_rate']:.2f} | {r['citation_validity_rate']:.2f} "
            f"| {r['routing_accuracy']:.2f} | {r['latency_p50_ms']:.0f} "
            f"| {r['latency_p95_ms']:.0f} | ${r['dollars_per_query']:.6f} "
            f"| {r['license']} | {r['portability']} |"
        )
    return lines


def _sql_section(result: dict) -> list[str]:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in result["sql"]:
        totals[row["model"]][0] += int(row["runnable"])
        totals[row["model"]][1] += 1
    lines = [
        "| Model | Runnable / total |",
        "|---|---|",
        *(f"| {m} | {ok} / {n} |" for m, (ok, n) in totals.items()),
    ]
    return lines


def _registry_rows(models: list[dict]) -> list[str]:
    lines = [
        "| Model | Slug | License | Portability | $/1M in | $/1M out | Price confidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in models:
        lines.append(
            f"| {m['id']} | `{m['slug']}` | {m['license']} | {m['portability']} "
            f"| {m['usd_per_1m_input']} | {m['usd_per_1m_output']} | {m['price_confidence']} |"
        )
    return lines


def render_report(
    result: dict,
    *,
    dry_run: bool,
    provider: str = "openrouter",
    models: list[dict] | None = None,
    path: Path = REPORT_PATH,
    today: date | None = None,
) -> Path:
    """Write the comparison report for a run_study result and return its path."""
    models = models if models is not None else load_models()
    today = today or date.today()
    if dry_run:
        status = (
            "> **DRY-RUN (placeholder numbers).** Produced at $0 by the canned `DryRunLLM`; "
            "these figures show the format only and say nothing about the models. "
            f"Generated {today.isoformat()}."
        )
    else:
        status = f"> **Real gated run** on {today.isoformat()} via provider `{provider}`."
    gt = GROUND_TRUTH.parent.relative_to(REPO_ROOT).as_posix()
    body = [
        "# Model comparison study (B-8)",
        "",
        status,
        "",
        "## Results",
        "",
        *_table(result["models"]),
        "",
        "## Descriptive SQL (descriptive, not gated)",
        "",
        "Count of SQL questions whose emitted SQL passed the read-only SELECT guard and ran on the "
        "scoped Gold table. Reported for information; no threshold applies.",
        "",
        *_sql_section(result),
        "",
        "## Methodology",
        "",
        "- **One axis varied: the generation model.** Embeddings, retrieval, SQL engine, prompts "
        "and judge are held fixed.",
        "- **Judge:** deterministic and $0 (model-agnostic), which avoids judge-model bias.",
        "- **Latency** reflects the B-11 index-hitting (HNSW) serving path.",
        "- **$/query** = token usage x the per-model price in `models.json`. It is an estimate: "
        "the audit holds one worst-case total (prompt estimate + `max_tokens` reservation), "
        "split into input (total minus the reservation) and output (estimated answer tokens).",
        "- Routing accuracy and SQL runnability are reported, not gated.",
        "",
        "## Models & pricing",
        "",
        *_registry_rows(models),
        "",
        "Prices are provisional; re-confirm live against OpenRouter before the paid run. "
        f"Source notes: `{gt}/models.README.md`.",
        "",
        "The large Mistral (Mistral Small 3.1 24B, 2503) is a different vintage than its 2512 "
        "small and medium siblings, so the Mistral family trend is not a clean size sweep.",
        "",
        "## Golden sets",
        "",
        f"Committed under `{gt}/`: `answers.json`, `study_routing.json`, `study_sql.json`.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body), encoding="utf-8")
    return path
