"""Model-comparison study runner: answer golden set through each registry model."""

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
from deltalake.exceptions import TableNotFoundError

from agents.composer import compose
from agents.docs_rag import docs_rag
from agents.llm import LLM, estimate_tokens, get_llm
from agents.pipeline import PipelineError
from agents.router import derive_scope, route
from agents.sql_agent import SQLGenerationUnavailable, UnsafeSQLError, generate_sql, run_sql
from app.config import get_settings
from app.cost import CostLedger
from eval.answer_eval import GROUND_TRUTH, judge_deterministic
from eval.metrics import mean, percentile
from eval.report import COST_PATH, REPORT_PATH, estimate_spend, render_report
from eval.study_cost import dollars_for, load_models
from governance.grounding import enforce_grounding
from retrieval.embeddings import GoAheadRequired

ROUTING_SET = GROUND_TRUTH.with_name("study_routing.json")
SQL_SET = GROUND_TRUTH.with_name("study_sql.json")
STUDY_ROLE = "analyst"  # unrestricted scope: the sub-runs measure the model, not the policy
CITE_MARKER = re.compile(r"\[(\d+)\]")
STATIC_KEYS = ("slug", "family", "tier", "license", "portability")
DRY_RUN_ANSWER = "The retrieved policy documents support this answer. [1]"


class DryRunLLM:
    """$0 stand-in: canned cited answer, ledger charged tokens but never dollars."""

    available = True

    async def complete(
        self, system: str, user: str, *, ledger: CostLedger, max_tokens: int | None = None
    ) -> str:
        ledger.add(
            estimate_tokens(system, user) + (max_tokens or get_settings().llm_max_tokens), 0.0
        )
        return DRY_RUN_ANSWER


def _require_go_ahead() -> None:
    """compose swallows GoAheadRequired into an extractive fallback, which would make a refused
    paid run look like a successful free one - so refuse up front instead."""
    s = get_settings()
    if s.provider_mode == "openrouter" and not (s.openrouter_go_ahead and s.openrouter_api_key):
        raise GoAheadRequired(
            "Model study requires human go-ahead: set OPENROUTER_GO_AHEAD=true and "
            "OPENROUTER_API_KEY, or pass dry_run=True for a $0 run."
        )


async def _answer(query: str, role: str, llm: LLM):
    """answer_docs' body (scope -> docs_rag -> compose) with the per-model client injected.

    answer_eval.answer_docs hard-wires compose's get_llm(); compose now takes an optional `llm`,
    so each model gets its own client with no settings mutation.
    """
    started = time.perf_counter()
    ledger = CostLedger()
    try:
        hits = await asyncio.to_thread(docs_rag, query, derive_scope(role))
        result = await compose(query, None, hits, ledger, llm=llm)
    except GoAheadRequired:
        raise
    except Exception as exc:
        raise PipelineError(f"{type(exc).__name__}: {exc}") from exc
    result.audit.update(
        tokens=ledger.tokens,
        cost_usd=ledger.usd,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return result


def _split_tokens(total: int, answer: str) -> tuple[int, int]:
    """The audit holds one total, a worst-case reservation (prompt estimate + max_tokens).
    Output is the answer's estimated tokens; input is the total minus the max_tokens reserve."""
    return max(total - get_settings().llm_max_tokens, 0), estimate_tokens(answer) if total else 0


def _citation_validity(answer: str, ns: set[int]) -> float:
    """1.0 when every [n] marker in the answer resolves to a returned citation, else 0.0.
    An answer with no markers is vacuously valid only if it also returned no citations
    (e.g. a refusal); citations the text never uses count as invalid too."""
    marked = {int(n) for n in CITE_MARKER.findall(answer)}
    return float(marked <= ns and bool(marked) == bool(ns))


async def _routing_accuracy(llm: LLM) -> float:
    """Share of routing cases where route() (rules miss by construction -> LLM) matches."""
    cases = json.loads(ROUTING_SET.read_text(encoding="utf-8"))
    hits = []
    for case in cases:
        decision = await route(case["question"], STUDY_ROLE, CostLedger(), llm=llm)
        hits.append(float(decision.intent == case["expected_intent"]))
    return mean(hits)


async def _sql_rows(model: dict, llm: LLM) -> list[dict]:
    """Descriptive only, no gate. `runnable` = the emitted SQL passes the read-only SELECT guard
    and executes without error on the scoped Gold table (run_sql, rows discarded). Unavailable
    generation or a missing Gold table records sql="" / runnable=False rather than aborting.
    """
    cases = json.loads(SQL_SET.read_text(encoding="utf-8"))
    scope = derive_scope(STUDY_ROLE)
    rows = []
    for case in cases:
        row = {"model": model["id"], "question": case["question"], "sql": "", "runnable": False}
        try:
            row["sql"] = await generate_sql(case["question"], CostLedger(), llm=llm)
            run_sql(row["sql"], scope)
            row["runnable"] = True
        except (
            SQLGenerationUnavailable,
            TableNotFoundError,
            FileNotFoundError,
            UnsafeSQLError,
            duckdb.Error,
        ):
            pass
        rows.append(row)
    return rows


async def _run_model(model: dict, cases: list[dict], llm: LLM) -> dict:
    scores, grounded, valid, latencies, dollars, tokens = [], [], [], [], [], []
    for case in cases:
        try:
            result = await _answer(case["question"], case["role"], llm)
        except PipelineError:
            # Same convention as evaluate_answers: an unanswerable case is a quality miss.
            scores.append(0.0), grounded.append(0.0), valid.append(0.0)
            latencies.append(0.0), dollars.append(0.0), tokens.append(0)
            continue
        audit = result.audit
        ns = {c.n for c in result.citations}
        scores.append(
            judge_deterministic(
                result.answer, result.citations, audit["grounding"], case["must_include"]
            )
        )
        # Same boolean as judge_deterministic's grounded term.
        grounded.append(
            float(
                audit["grounding"].get("path") != "none"
                and bool(ns)
                and not enforce_grounding(result.answer, ns)
            )
        )
        valid.append(_citation_validity(result.answer, ns))
        latencies.append(audit["latency_ms"])
        tokens.append(audit["tokens"])
        in_tok, out_tok = _split_tokens(audit["tokens"], result.answer)
        dollars.append(dollars_for(model, in_tok, out_tok))
    return {
        **{k: model[k] for k in STATIC_KEYS},
        "id": model["id"],
        "faithfulness": mean(scores),
        "grounded_path_rate": mean(grounded),
        "citation_validity_rate": mean(valid),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "dollars_per_query": mean(dollars),
        "tokens": mean(tokens),
        "routing_accuracy": await _routing_accuracy(llm),
    }


async def run_study(models: list[dict], *, dry_run: bool = False) -> dict:
    """Run every answers.json case through each model, plus the routing and descriptive-SQL
    sub-runs; returns {"models": [row, ...], "sql": [{model, question, sql, runnable}, ...]}."""
    if not dry_run:
        _require_go_ahead()
    cases = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    rows, sql_rows = [], []
    for model in models:
        llm = DryRunLLM() if dry_run else get_llm(model=model["slug"])
        rows.append(await _run_model(model, cases, llm))
        sql_rows.extend(await _sql_rows(model, llm))
    return {"models": rows, "sql": sql_rows}


def log_spend(result: dict, estimate: float, path: Path = COST_PATH) -> float:
    """Append the actual answer-path spend (sum of per-query $ over the answer cases) to COST.md.
    Routing and SQL calls are not in dollars_per_query, so the estimate bounds the rest."""
    cases = len(json.loads(GROUND_TRUTH.read_text(encoding="utf-8")))
    actual = sum(r["dollars_per_query"] for r in result["models"]) * cases
    row = (
        f"| {date.today().isoformat()} | B-8 | OpenRouter: B-8 model-comparison study run "
        f"({len(result['models'])} models; answer-path actual) | {estimate:.4f} | {actual:.4f} |"
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("|"))
    end = start
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    lines.insert(end, row)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return actual


def _print_estimate(est: dict) -> None:
    print(f"Spend estimate (worst case, {est['calls']} calls):")
    for model_id, usd in est["per_model"].items():
        print(f"  {model_id:<26} ${usd:.4f}")
    print(f"  {'TOTAL':<26} ${est['total']:.4f}")


async def execute(
    *, live: bool, report_path: Path = REPORT_PATH, cost_path: Path = COST_PATH
) -> int:
    """Print the estimate, then run. Dry-run is $0 and writes no COST.md line; a live run needs
    PROVIDER_MODE=openrouter + OPENROUTER_GO_AHEAD + key and logs its actual spend."""
    models = load_models()
    est = estimate_spend(models)
    _print_estimate(est)
    if not live:
        result = await run_study(models, dry_run=True)
        render_report(result, dry_run=True, models=models, path=report_path)
        print(f"DRY-RUN: $0 spent; sample report written to {report_path}")
        return 0
    try:
        if get_settings().provider_mode != "openrouter":
            raise GoAheadRequired("A live study needs PROVIDER_MODE=openrouter.")
        result = await run_study(models)
    except GoAheadRequired as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    render_report(result, dry_run=False, provider="openrouter", models=models, path=report_path)
    actual = log_spend(result, est["total"], cost_path)
    print(f"LIVE run done: answer-path actual ${actual:.4f}; logged to {cost_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B-8 model-comparison study")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="$0 sample run (default)")
    mode.add_argument("--live", action="store_true", help="paid run; needs the env go-ahead")
    args = parser.parse_args(argv)
    return asyncio.run(execute(live=args.live))


if __name__ == "__main__":
    sys.exit(main())
