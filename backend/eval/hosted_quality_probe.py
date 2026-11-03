"""Explicitly authorized, read-only OpenRouter extension of the M7 baseline.

Dedicated CLI process only. Never import this context into the serving app.
Reservations are retained even after errors, across every turn and ledger.
"""

import argparse
import asyncio
import json
import math
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import httpx
import psycopg

from agents import llm, pipeline
from app.config import Settings
from eval import quality_baseline as baseline


class ProbeLimit(RuntimeError):
    """Run-wide reservation or call limit reached before sending a request."""


class Budget:
    def __init__(self, prices: dict, cap: float, max_calls: int = 60) -> None:
        if not 0 < cap <= 2 or not 0 < max_calls <= 60:
            raise ValueError("Approved limits: $2 and 60 requests maximum")
        self.prices = prices
        self.cap = cap
        self.max_calls = max_calls
        self.reserved = 0.0
        self.calls: list[dict] = []

    def reserve(self, payload: dict) -> dict:
        model = payload.get("model")
        if model not in self.prices:
            raise ProbeLimit("Unpriced model refused")
        prompt_price, output_price = self.prices[model]
        # UTF-8 bytes conservatively bound text tokens; extra framing allowance.
        # Keep a further 4x margin. Only plain text messages are permitted.
        text = json.dumps(payload["messages"], ensure_ascii=False)
        input_bound = 4 * len(text.encode("utf-8")) + 4096
        output_bound = int(payload["max_tokens"])
        if not 0 < output_bound <= 1024:
            raise ProbeLimit("Unexpected output limit")
        amount = input_bound * prompt_price + output_bound * output_price
        if len(self.calls) >= self.max_calls or self.reserved + amount > self.cap:
            raise ProbeLimit("Run-wide budget exhausted")
        self.reserved += amount
        record = {"model": model, "reserved_usd": amount, "status": "reserved"}
        self.calls.append(record)
        return record

    def report(self) -> dict:
        return {
            "cap_usd": self.cap,
            "reserved_upper_usd": self.reserved,
            "provider_reported_usd": sum(c.get("provider_cost_usd", 0) for c in self.calls),
            "provider_cost_coverage": sum("provider_cost_usd" in c for c in self.calls),
            "requests": len(self.calls),
            "calls": self.calls,
        }


def prices_for(settings: Settings) -> dict:
    models = {settings.openrouter_model} | {
        getattr(settings, "openrouter_model_" + tier) for tier in ("small", "medium", "large")
    }
    models.discard(None)
    response = httpx.get(settings.openrouter_base_url.rstrip("/") + "/models", timeout=20)
    response.raise_for_status()
    prices = {}
    for model in response.json()["data"]:
        if model["id"] not in models:
            continue
        pricing = model["pricing"]
        pair = tuple(float(pricing[key]) for key in ("prompt", "completion"))
        if any(not math.isfinite(p) or p < 0 for p in pair):
            raise ProbeLimit("Invalid model price")
        # Refuse per-request, image, search or other billing surfaces.
        if any(
            float(v) != 0
            for k, v in pricing.items()
            if k not in ("prompt", "completion", "input_cache_read", "input_cache_write")
        ):
            raise ProbeLimit("Additional model charges refused")
        # Double the published rate, with an explicit server-side price ceiling.
        prices[model["id"]] = tuple(p * 2 for p in pair)
    if set(prices) != models:
        raise ProbeLimit("Configured model missing from price catalogue")
    return prices


@contextmanager
def authorized_probe(settings: Settings, budget: Budget, journal: Path):
    if settings.provider_mode != "openrouter" or not settings.openrouter_go_ahead:
        raise ProbeLimit("Requires existing authorized OpenRouter configuration")
    if not settings.openrouter_api_key or settings.vector_store != "pgvector":
        raise ProbeLimit("Existing credentials and pgvector required")
    if settings.reranker == "azure":
        raise ProbeLimit("Paid reranking not authorized")
    original_connect = psycopg.connect
    original_answer = pipeline.answer

    def readonly_connect(*args, **kwargs):
        kwargs["options"] = "-c default_transaction_read_only=on -c statement_timeout=30000"
        kwargs["connect_timeout"] = 10
        return original_connect(*args, **kwargs)

    def prerequisites(s):
        if not s.database_url or not baseline.sql_agent.gold_structured_path().exists():
            return "Existing database and structured Gold required"
        return None

    def checkpoint():
        journal.write_text(json.dumps(budget.report(), indent=2) + "\n")

    async def guarded_chat(url, headers, payload, *, timeout=60):
        if url != settings.openrouter_base_url.rstrip("/") + "/chat/completions":
            raise ProbeLimit("Unexpected generation endpoint")
        record = budget.reserve(payload)
        checkpoint()
        prompt_price, output_price = budget.prices[payload["model"]]
        payload = {
            **payload,
            "provider": {
                "max_price": {
                    "prompt": prompt_price * 1_000_000,
                    "completion": output_price * 1_000_000,
                }
            },
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()
            choice, usage = data["choices"][0], data.get("usage")
            record.update(
                status="completed", finish_reason=choice.get("finish_reason"), usage=usage
            )
            if usage and usage.get("cost") is not None:
                record["provider_cost_usd"] = float(usage["cost"])
            return choice["message"]["content"], usage
        except Exception as exc:
            record.update(status="error", error_type=type(exc).__name__)
            raise
        finally:
            checkpoint()

    async def progress_answer(query, role, **kwargs):
        print(f"Testing {role}: {query}", flush=True)
        return await original_answer(query, role, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(baseline, "live_prerequisites", prerequisites))
        stack.enter_context(patch.object(psycopg, "connect", readonly_connect))
        stack.enter_context(patch.object(llm, "_chat", guarded_chat))
        stack.enter_context(patch.object(pipeline, "answer", progress_answer))
        yield


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize-hosted", action="store_true", required=True)
    parser.add_argument("--budget-usd", type=float, required=True)
    parser.add_argument("--cases", nargs="+", default=["A01", "A02", "A03", "A04", "A05", "A06"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error("Live artifacts must remain outside repository")
    if not 0 < args.budget_usd <= 2:
        parser.error("Budget must be positive and at most $2")
    settings = Settings()
    # Validate provider before fetching any metadata.
    if settings.provider_mode != "openrouter" or not settings.openrouter_api_key:
        parser.error("Existing OpenRouter credentials required")
    budget = Budget(prices_for(settings), args.budget_usd)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with authorized_probe(settings, budget, args.output.with_suffix(".budget.json")):
        report = asyncio.run(baseline.run("live", set(args.cases)))
    report["budget"] = budget.report()
    report["limitations"].append("Hosted calls authorized up to $2; source state read-only.")
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    args.output.with_suffix(".md").write_text(baseline.markdown(report))
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "budget": {k: v for k, v in budget.report().items() if k != "calls"},
            }
        )
    )
    return baseline.exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
