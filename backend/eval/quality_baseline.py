"""Observe the real pipeline in a dedicated process; never use in a serving process.

Synthetic mode substitutes external adapters, NOT routing/memory/SQL/composition logic.
Live mode is read-only except for ephemeral in-process conversation storage.
"""

import argparse
import asyncio
import hashlib
import ipaddress
import json
import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
import psycopg

from agents import (
    composer,
    conversation,
    llm,
    model_policy,
    pipeline,
    query_plan,
    router,
    sql_agent,
)
from app import config, cost
from eval.quality_fixture import (
    EphemeralMemoryStore,
    FixtureLLM,
    FixtureStore,
    fixture_connection,
    load_fixture,
)
from governance.grounding import citation_numbers
from governance.pii import redact
from governance.policy import scope_for_role
from memory import manager
from retrieval import embeddings, hybrid, rerank, vector_store

CASES = Path(__file__).parent / "ground_truth" / "quality_cases.json"
MODULES = (
    composer,
    conversation,
    llm,
    model_policy,
    query_plan,
    pipeline,
    router,
    sql_agent,
    manager,
    embeddings,
    hybrid,
    rerank,
    vector_store,
    config,
    cost,
)


def load_catalogue() -> dict:
    return json.loads(CASES.read_text())


def check(name: str, ok: bool | None, reason: str) -> dict:
    status = "NOT RUN" if ok is None else "PASS" if ok else "FAIL"
    return {"name": name, "status": status, "reason": reason}


def verdict(checks: list[dict]) -> str:
    statuses = {c["status"] for c in checks}
    return "FAIL" if "FAIL" in statuses else "NOT RUN" if "NOT RUN" in statuses else "PASS"


def exit_code(report: dict) -> int:
    statuses = {row["status"] for row in report["results"]}
    return 1 if "FAIL" in statuses else 2 if "NOT RUN" in statuses else 0


def unavailable(exc: Exception) -> bool:
    """Known live prerequisites only; programming and semantic failures remain FAIL."""
    while exc.__cause__ is not None:
        exc = exc.__cause__
    return isinstance(exc, (OSError, ImportError, httpx.HTTPError, psycopg.OperationalError))


def live_prerequisites(settings: config.Settings) -> str | None:
    """No provider calls or secret output during preflight."""
    if settings.provider_mode != "free" or settings.free_llm_api_key:
        return "Requires free mode and a keyless loopback LLM; paid calls refused."
    url = urlsplit(settings.free_llm_base_url or "")
    host = url.hostname or ""
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "localhost"
    if (
        not loopback
        or url.scheme not in ("http", "https")
        or url.username
        or url.password
        or not settings.free_llm_model
    ):
        return "No configured keyless loopback LLM; remote endpoints refused."
    if settings.vector_store != "pgvector" or settings.database_url is None:
        return "Existing pgvector corpus/database configuration required."
    if not sql_agent.gold_structured_path().exists():
        return "Existing structured Gold unavailable; runner never creates it."
    return None


@contextmanager
def environment(mode: str, fixture: dict) -> Iterator[None]:
    """All scoped adapter/settings replacements are restored on exit."""
    settings = config.Settings.model_construct() if mode == "fixture" else config.Settings()
    settings = settings.model_copy(
        update={
            "audit_enabled": False,
            "observability_enabled": False,
            "memory_enabled": True,
            "source_review_fallback": mode != "fixture",
        }
    )
    memory = EphemeralMemoryStore()
    with ExitStack() as stack:
        for module in MODULES:
            if hasattr(module, "get_settings"):
                stack.enter_context(patch.object(module, "get_settings", return_value=settings))
        stack.enter_context(patch.object(pipeline, "ensure_memory_schema", return_value=None))
        stack.enter_context(
            patch.object(
                pipeline, "MemoryManager", side_effect=lambda: manager.MemoryManager(store=memory)
            )
        )
        stack.enter_context(patch.object(pipeline, "_start_trace", return_value=None))
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "HF_HUB_OFFLINE": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                },
            )
        )
        if mode == "fixture":
            store, scripted = FixtureStore(fixture), FixtureLLM()
            for module in (router, sql_agent, composer, conversation, manager):
                stack.enter_context(patch.object(module, "get_llm", return_value=scripted))
            stack.enter_context(patch.object(hybrid, "get_vector_store", return_value=store))
            stack.enter_context(patch.object(hybrid, "get_embedder", return_value=store.embedder))
            stack.enter_context(
                patch.object(hybrid, "get_reranker", return_value=rerank.NoReranker())
            )
            stack.enter_context(
                patch.object(
                    sql_agent,
                    "_connect",
                    side_effect=lambda scope=None: fixture_connection(fixture, scope),
                )
            )
            stack.enter_context(
                patch.object(
                    sql_agent,
                    "_columns",
                    return_value=[
                        "asin",
                        "category",
                        "rating",
                        "year",
                        "timestamp",
                        "product_title",
                    ],
                )
            )
            stack.enter_context(
                patch(
                    "socket.socket.connect",
                    side_effect=RuntimeError("Network forbidden in synthetic baseline"),
                )
            )
            stack.enter_context(
                patch(
                    "psycopg.connect",
                    side_effect=RuntimeError("Postgres forbidden in synthetic baseline"),
                )
            )
        yield


@contextmanager
def capture() -> Iterator[dict]:
    """Observe the real tool inputs/outputs without altering their decisions."""
    observation = {"retrieved": [], "sql": None, "resolved_query": None}
    original_route, original_sql = pipeline.route, pipeline.sql_agent

    async def observed_route(query, *args, **kwargs):
        observation["resolved_query"] = query
        decision = await original_route(query, *args, **kwargs)
        observation["decision"] = decision.model_dump()
        return decision

    async def observed_sql(*args, **kwargs):
        result = await original_sql(*args, **kwargs)
        observation["sql"] = result
        observation["selected_product_ids"] = (
            [row[result["columns"].index("asin")] for row in result["rows"]]
            if "asin" in result["columns"]
            else []
        )
        return result

    def observe_rag(original):
        def observed(*args, **kwargs):
            hits = original(*args, **kwargs)
            observation["retrieved"].extend(
                [
                    {
                        "id": h.chunk.id,
                        "category": h.chunk.category,
                        "asin": h.chunk.asin,
                        "source_type": h.chunk.source_type,
                        "doc_id": h.chunk.doc_id,
                        "section": h.chunk.section,
                        "text": h.chunk.text,
                        "score": h.score,
                    }
                    for h in hits
                ]
            )
            return hits

        return observed

    with ExitStack() as stack:
        stack.enter_context(patch.object(pipeline, "route", side_effect=observed_route))
        stack.enter_context(patch.object(pipeline, "sql_agent", side_effect=observed_sql))
        for name in ("review_rag", "docs_rag", "selected_source_reviews"):
            stack.enter_context(
                patch.object(pipeline, name, side_effect=observe_rag(getattr(pipeline, name)))
            )
        yield observation


def assess(
    case: dict, role: str, observation: dict, result, fixture: dict, mode: str, setup: list[dict]
) -> list[dict]:
    """Independent assertions. Citation references are never called faithfulness."""
    audit = result.audit
    checks = [
        check(
            "required tools",
            set(case["tools"]) <= set(audit.get("tool_path", [])),
            f"Expected {case['tools']}; observed {audit.get('tool_path', [])}.",
        )
    ]
    if case.get("standalone"):
        checks.append(
            check(
                "standalone query",
                observation["resolved_query"] == case["question"],
                "Complete questions must not inherit unrelated prior questions.",
            )
        )
    reviews = [h for h in observation["retrieved"] if h["source_type"] == "review"]
    scope = scope_for_role(role).get("category")
    sql = observation["sql"]
    scope_ok = all(not scope or h["category"] in scope for h in reviews)
    if sql and "category" in sql["columns"]:
        col = sql["columns"].index("category")
        scope_ok &= all(not scope or row[col] in scope for row in sql["rows"])
    checks.append(
        check(
            "observable scope",
            scope_ok,
            "Returned review categories and projected SQL category columns only.",
        )
    )
    if sql and "category" not in sql["columns"]:
        checks.append(
            check(
                "SQL product scope",
                None,
                "Projection omits category; independent product provenance join pending.",
            )
        )
    category = case.get("category")
    if category and "review_rag" in case["tools"]:
        allowed = not scope or category in scope
        category_ok = (
            bool(reviews) and all(h["category"] == category for h in reviews)
            if allowed
            else not reviews
        )
        checks.append(
            check(
                "requested category",
                category_ok,
                "Requested category must constrain evidence within access scope.",
            )
        )
    sql_check = case.get("sql_check")
    if sql_check == "averages":
        if mode != "fixture":
            checks.append(
                check(
                    "numeric gold",
                    None,
                    "Synthetic gold does not describe live data; snapshot required.",
                )
            )
        else:
            expected = {k: v for k, v in fixture["averages"].items() if not scope or k in scope}
            actual = {}
            if sql and "category" in sql["columns"] and "avg_rating" in sql["columns"]:
                ci, vi = sql["columns"].index("category"), sql["columns"].index("avg_rating")
                actual = {r[ci]: r[vi] for r in sql["rows"]}
            checks.append(
                check(
                    "numeric gold", actual == expected, f"Expected {expected}; observed {actual}."
                )
            )
    if sql_check == "lowest":
        selected = set()
        if sql and "asin" in sql["columns"]:
            selected = {r[sql["columns"].index("asin")] for r in sql["rows"]}
        if mode == "fixture":
            expected_ids = set(fixture["lowest"][category])
            checks.append(
                check(
                    "selected product gold",
                    selected == expected_ids,
                    f"Expected {sorted(expected_ids)}; observed {sorted(selected)}.",
                )
            )
        else:
            checks.append(
                check(
                    "selected product gold",
                    None,
                    "Live selection requires independently verified product gold.",
                )
            )
        checks.append(
            check(
                "product evidence join",
                bool(selected) and bool(reviews) and all(h["asin"] in selected for h in reviews),
                "Explanation evidence must belong to the selected products.",
            )
        )
    if sql_check == "empty":
        if mode == "fixture":
            checks.append(
                check(
                    "empty fixture selection",
                    sql is not None and not sql["rows"],
                    "UnknownCategory is absent from the authored fixture.",
                )
            )
        if sql is not None and not sql["rows"]:
            checks.append(
                check(
                    "empty is not evidence",
                    result.sql is None and not any(c.source_id == "sql" for c in result.citations),
                    "Zero-row outcomes must not become a supporting SQL source/table.",
                )
            )
        else:
            checks.append(check("empty is not evidence", None, "No empty selection observed."))
    if case["id"] == "A12":
        checks.append(
            check(
                "clarification resolved",
                bool(setup)
                and setup[0].get("kind") == "clarification"
                and result.kind != "clarification",
                "First turn clarifies; concrete reply must not clarify again.",
            )
        )
    used = citation_numbers(result.answer)
    checks.append(
        check(
            "citation references",
            used <= {c.n for c in result.citations},
            "Reference integrity only, not factual support.",
        )
    )
    checks.append(
        check(
            "qualitative support",
            None,
            "Requires reviewer judgment against captured source bodies.",
        )
    )
    if case["id"] in ("A08", "A09"):
        checks.append(check("browser semantics", None, "No browser executed."))
    if mode == "fixture":
        checks.append(
            check(
                "live generation and retrieval",
                None,
                "Scripted LLM and bag-of-words adapters; not production embeddings.",
            )
        )
    return checks


def scrub(value: Any) -> Any:
    """Allowlisted observations only; no settings, credentials or exception messages."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    return value


async def run(mode: str = "fixture", case_ids: set[str] | None = None) -> dict:
    if mode not in ("fixture", "live"):
        raise ValueError("mode must be fixture or live")
    catalogue, fixture = load_catalogue(), load_fixture()
    selected = [c for c in catalogue["cases"] if case_ids is None or c["id"] in case_ids]
    known = {c["id"] for c in catalogue["cases"] + catalogue["boundaries"]}
    if case_ids and case_ids - known:
        raise ValueError("Unknown acceptance case ID")
    reason = live_prerequisites(config.Settings()) if mode == "live" else None
    report = {
        "mode": mode,
        "fixture_version": fixture["version"] if mode == "fixture" else None,
        "catalogue_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
        "coverage": (
            fixture["coverage"] if mode == "fixture" else "Existing corpus; not snapshotted"
        ),
        "limitations": [
            "No browser or semantic-support reviewer executed.",
            "Ephemeral memory: DB ownership/persistence and cross-thread findings untested.",
            "Finish reason and source/index versions not exposed by runtime adapters.",
        ],
        "results": [],
    }
    if mode == "fixture":
        report["limitations"].append("Synthetic contracts, not real LLM/embedding quality.")
    with environment(mode, fixture):
        for case in selected:
            for role in catalogue["roles"]:
                row = {
                    "id": case["id"],
                    "role": role,
                    "expectation": case["expectation"],
                    "question": case["question"],
                    "setup": [],
                    "observation": {},
                }
                if reason:
                    row["checks"] = [check("live prerequisites", None, reason)]
                else:
                    try:
                        thread = f"baseline-{case['id']}-{role}"
                        setup_questions = case.get("setup_by_role", {}).get(role, case["setup"])
                        for question in setup_questions:
                            previous = await pipeline.answer(
                                question, role, thread_id=thread, user_id=thread
                            )
                            row["setup"].append(
                                {
                                    "question": question,
                                    "kind": previous.kind,
                                    "answer": previous.answer,
                                    "memory": previous.audit.get("memory"),
                                }
                            )
                        with capture() as observed:
                            row["observation"] = observed
                            result = await pipeline.answer(
                                case["question"], role, thread_id=thread, user_id=thread
                            )
                        row["observation"] = observed
                        row["response"] = {
                            "kind": result.kind,
                            "answer": result.answer,
                            "citations": [c.model_dump() for c in result.citations],
                            "sql": result.sql.model_dump() if result.sql else None,
                            "audit": {
                                k: result.audit.get(k)
                                for k in (
                                    "intent",
                                    "tool_path",
                                    "scope",
                                    "grounding",
                                    "sources",
                                    "memory",
                                    "tokens",
                                    "cost_usd",
                                    "latency_ms",
                                )
                            },
                        }
                        row["checks"] = assess(
                            case, role, observed, result, fixture, mode, row["setup"]
                        )
                        if result.audit.get("memory", {}).get("error"):
                            row["checks"].append(
                                check("sequence memory", False, "Memory failed; sequence invalid.")
                            )
                        if any((turn.get("memory") or {}).get("error") for turn in row["setup"]):
                            row["checks"].append(
                                check(
                                    "setup memory", False, "Setup memory failed; sequence invalid."
                                )
                            )
                        if result.audit.get("sql_error"):
                            row["checks"].append(
                                check(
                                    "SQL execution", False, "Tool could not compute this request."
                                )
                            )
                    except Exception as exc:
                        row["checks"] = [
                            check(
                                "pipeline execution",
                                None if mode == "live" and unavailable(exc) else False,
                                f"Execution failed: {type(exc).__name__}; "
                                "not counted as successful coverage.",
                            )
                        ]
                row["status"] = verdict(row["checks"])
                report["results"].append(row)
    for boundary in catalogue["boundaries"]:
        if case_ids is None or boundary["id"] in case_ids:
            report["results"].append(
                {
                    **boundary,
                    "role": "both",
                    "status": "NOT RUN",
                    "checks": [check("boundary instrumentation", None, boundary["reason"])],
                }
            )
    report["summary"] = {
        status: sum(r["status"] == status for r in report["results"])
        for status in ("PASS", "FAIL", "NOT RUN")
    }
    report["assertions"] = {
        status: sum(c["status"] == status for r in report["results"] for c in r["checks"])
        for status in ("PASS", "FAIL", "NOT RUN")
    }
    return scrub(report)


def markdown(report: dict) -> str:
    lines = [
        "# Answer-quality baseline",
        "",
        f"Mode: **{report['mode']}**.",
        "",
        report["coverage"],
        "",
        "No aggregate faithfulness score is claimed.",
        "",
    ]
    lines += [f"- {item}" for item in report["limitations"]]
    lines += [
        "",
        f"Cases: {report['summary']}",
        f"Assertions: {report['assertions']}",
        "",
        "| Case | Role | Status | Failed or unmeasured checks |",
        "|---|---|---|---|",
    ]
    for row in report["results"]:
        details = "; ".join(
            f"{c['name']}: {c['status']}" for c in row["checks"] if c["status"] != "PASS"
        )
        lines.append(f"| {row['id']} | {row['role']} | {row['status']} | {details} |")
    lines += [
        "",
        "See companion JSON for expectations, assertion reasons and evidence.",
        "Synthetic results must not be presented as live answer-quality validation.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--cases", nargs="+", help="A01 … A22; omit for all")
    parser.add_argument("--output", type=Path, required=True, help="Artifact path stem")
    args = parser.parse_args(argv)
    if args.mode == "live":
        repo = Path(__file__).resolve().parents[2]
        if args.output.resolve().is_relative_to(repo):
            parser.error("Live artifacts must be written outside the repository")
    report = asyncio.run(run(args.mode, set(args.cases) if args.cases else None))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    args.output.with_suffix(".md").write_text(markdown(report))
    print(json.dumps({"mode": report["mode"], **report["summary"]}))
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
