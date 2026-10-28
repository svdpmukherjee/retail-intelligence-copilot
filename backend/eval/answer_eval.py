"""Answer-quality harness: judged faithfulness plus per-query cost/latency/tokens from the audit."""

import asyncio
import json
import re
import time
from pathlib import Path

from agents.composer import AnswerResult, Citation, compose
from agents.docs_rag import docs_rag
from agents.llm import get_llm
from agents.pipeline import PipelineError
from agents.router import derive_scope
from app.config import get_settings
from app.cost import CostLedger
from eval.metrics import mean
from governance.grounding import enforce_grounding

GROUND_TRUTH = Path(__file__).parent / "ground_truth" / "answers.json"
GROUNDED_WEIGHT = 0.5

JUDGE_SYSTEM = (
    "You grade a retail copilot answer. Reply with only a number from 0 to 1: how faithful the "
    "answer is to its cited evidence and how fully it contains the expected facts."
)


def judge_deterministic(
    answer: str, citations: list[Citation], grounding: dict, must_include: list[str]
) -> float:
    """$0 judge: 0.5 * grounded + 0.5 * keyword coverage.

    Grounded (1.0 or 0.0) needs real evidence (grounding path not "none"), at least one resolvable
    citation, and a clean `enforce_grounding` pass - the same gate production applies, so the
    judge cannot disagree with it. Coverage is the share of gold `must_include` strings found
    (case-insensitive); the blend stops a cited-but-wrong or correct-but-uncited answer
    scoring high.
    """
    valid = {c.n for c in citations}
    grounded = float(
        grounding.get("path") != "none" and bool(valid) and not enforce_grounding(answer, valid)
    )
    text = answer.lower()
    coverage = (
        sum(kw.lower() in text for kw in must_include) / len(must_include) if must_include else 1.0
    )
    return GROUNDED_WEIGHT * grounded + (1 - GROUNDED_WEIGHT) * coverage


async def judge_llm(
    question: str, answer: str, citations: list[Citation], must_include: list[str]
) -> tuple[float, float]:
    """LLM-as-judge via get_llm() under its own CostLedger; returns (score, judge_cost_usd).

    Azure raises GoAheadRequired unless azure_llm_go_ahead is granted; never used on the $0 path.
    """
    ledger = CostLedger()
    cited = ", ".join(f"[{c.n}] {c.label}" for c in citations) or "none"
    user = (
        f"Question: {question}\nExpected facts: {', '.join(must_include)}\n"
        f"Citations: {cited}\nAnswer:\n{answer}"
    )
    reply = await get_llm().complete(JUDGE_SYSTEM, user, ledger=ledger, max_tokens=16)
    match = re.search(r"\d*\.?\d+", reply)
    score = min(max(float(match.group()), 0.0), 1.0) if match else 0.0
    return score, ledger.usd


async def answer_docs(query: str, role: str) -> AnswerResult:
    """Docs-RAG answer path with the intent pinned: scope -> docs_rag -> compose.

    The gold set measures answers over the authored docs. Pinning the intent keeps that
    measurement independent of the router (free mode has no LLM and misroutes policy questions
    to review_rag) and of any non-doc data in the DB. pipeline.answer has no intent override,
    so this mirrors its docs_rag branch and audit fields rather than editing it.
    """
    started = time.perf_counter()
    ledger = CostLedger()
    try:
        hits = await asyncio.to_thread(docs_rag, query, derive_scope(role))
        result = await compose(query, None, hits, ledger)
    except Exception as exc:
        raise PipelineError(f"{type(exc).__name__}: {exc}") from exc
    result.audit.update(
        tokens=ledger.tokens,
        cost_usd=ledger.usd,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
    )
    return result


async def evaluate_answers() -> dict:
    """Run every gold question through the docs-RAG path and judge it (judge per `eval_judge`)."""
    use_llm = get_settings().eval_judge == "llm"
    cases = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    per_question = []
    for case in cases:
        try:
            result = await answer_docs(case["question"], role=case["role"])
        except PipelineError as exc:
            # A question the pipeline cannot answer is a quality miss, not a harness crash.
            per_question.append(
                {
                    "question": case["question"],
                    "faithfulness": 0.0,
                    "cost_usd": 0.0,
                    "judge_cost_usd": 0.0,
                    "latency_ms": 0.0,
                    "tokens": 0,
                    "error": str(exc),
                }
            )
            continue
        judge_cost = 0.0
        if use_llm:
            score, judge_cost = await judge_llm(
                case["question"], result.answer, result.citations, case["must_include"]
            )
        else:
            score = judge_deterministic(
                result.answer,
                result.citations,
                result.audit["grounding"],
                case["must_include"],
            )
        per_question.append(
            {
                "question": case["question"],
                "faithfulness": score,
                "cost_usd": result.audit["cost_usd"],
                "judge_cost_usd": judge_cost,
                "latency_ms": result.audit["latency_ms"],
                "tokens": result.audit["tokens"],
            }
        )
    return {
        "faithfulness": mean([q["faithfulness"] for q in per_question]),
        "cost_per_query_usd": mean([q["cost_usd"] for q in per_question]),
        "per_question": per_question,
    }
