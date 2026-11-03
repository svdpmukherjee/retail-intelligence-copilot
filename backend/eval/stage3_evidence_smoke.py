"""Real offline embeddings/SQLite/Delta/pipeline smoke on synthetic sources only."""

import argparse
import asyncio
import json
import socket
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import psycopg

from agents import pipeline, sql_agent
from app.config import Settings
from retrieval import hybrid
from retrieval.embeddings import FreeEmbedder
from retrieval.evidence_bundle import (
    build_fixture_bundle,
    open_bundle,
    write_fixture_pointer,
)
from retrieval.index_docs import prepare_candidate_docs
from retrieval.index_reviews import prepare_candidate_reviews
from retrieval.provenance import content_hash, review_parent_id
from retrieval.selection import select_reviews
from retrieval.sufficiency import lexical_query


def fixture_rows() -> list[dict]:
    values = [
        (
            "battery-1",
            "P1",
            "Electronics",
            1,
            "Battery stopped charging after two days. The battery fails.",
        ),
        (
            "battery-2",
            "P1",
            "Electronics",
            2,
            "Battery would not charge. Update: the replacement fixed the charging problem.",
        ),
        (
            "praise-1",
            "P2",
            "Electronics",
            5,
            "The headphones sound clear and are very comfortable.",
        ),
        (
            "praise-2",
            "P2",
            "Electronics",
            4,
            "Headphones have excellent sound and comfortable cushions.",
        ),
        (
            "long",
            "P3",
            "Electronics",
            1,
            "The packaging arrived clean. " * 150 + "The battery leaked and burned the case.",
        ),
        (
            "book",
            "P4",
            "Books",
            5,
            "The cookbook has clear recipes and beautiful pictures.",
        ),
    ]
    return [
        {
            "review_id": key,
            "asin": asin,
            "category": category,
            "rating": float(rating),
            "title": "",
            "text": text,
            "year": 2023,
            "timestamp": "2023-01-01T00:00:00Z",
            "product_title": {
                "P1": "Battery device",
                "P2": "Headphones",
                "P3": "Power bank",
                "P4": "Cookbook",
            }[asin],
        }
        for key, asin, category, rating, text in values
    ]


async def run(output: Path) -> dict:
    settings = Settings(
        _env_file=None,
        provider_mode="free",
        embedding_local_files_only=True,
        free_llm_base_url=None,
        free_llm_model=None,
        database_url=None,
        openrouter_go_ahead=False,
        azure_llm_go_ahead=False,
        memory_enabled=False,
        audit_enabled=False,
        observability_enabled=False,
    )
    embedder = FreeEmbedder(settings)
    rows = fixture_rows()
    selected = select_reviews(
        rows, seed="stage3-frozen", diagnostic_products={("Electronics", "P1")}
    )
    parents, rejected = prepare_candidate_reviews(selected, "fixture:stage3-v1")
    docs, doc_rejected = prepare_candidate_docs(
        [
            (
                "return",
                "# Return policy\n## Damaged items\n"
                "Return items damaged on arrival within 30 days.",
            )
        ],
        "fixture:stage3-doc-v1",
    )
    assert not rejected and not doc_rejected
    structured = [
        {k: row[k] for k in ("asin", "category", "rating", "product_title", "year")} for row in rows
    ]
    report = {
        "mode": "isolated synthetic corpus, real cached embeddings/SQLite FTS/Delta/pipeline",
        "hosted_usd": 0,
        "generation": "disabled",
        "checks": [],
        "retrieval": [],
    }

    def check(name, condition):
        report["checks"].append({"name": name, "status": "PASS" if condition else "FAIL"})

    with tempfile.TemporaryDirectory(prefix="ric-stage3-fixture-") as directory:
        workspace = Path(directory)
        first = workspace / "v1"
        report["build"] = build_fixture_bundle(
            first,
            version="v1",
            parents=parents + docs,
            structured_rows=structured,
            embedder=embedder,
            seed="stage3-frozen",
        )
        store = open_bundle(first)
        report["embedding"] = store.manifest.embedding.model_dump()
        cases = [
            (
                "calibration",
                "battery stopped charging",
                {"category": ["Electronics"], "asin": ["P1"]},
                True,
            ),
            (
                "calibration",
                "quantum isotope reactor coolant",
                {"category": ["Electronics"]},
                False,
            ),
            (
                "heldout",
                "Why do customers complain about battery charging?",
                {"category": ["Electronics"], "asin": ["P1"]},
                True,
            ),
            (
                "heldout",
                "What do customers praise about headphone comfort?",
                {"category": ["Electronics"], "asin": ["P2"]},
                True,
            ),
            (
                "heldout",
                "What color is the submarine periscope?",
                {"category": ["Electronics"]},
                False,
            ),
            (
                "heldout",
                "Why do customers complain about a battery leaking?",
                {"category": ["Electronics"], "asin": ["P3"]},
                True,
            ),
        ]

        def forbidden(*args, **kwargs):
            raise AssertionError("Offline fixture must not connect to services")

        with ExitStack() as stack:
            stack.enter_context(patch.object(socket, "create_connection", forbidden))
            stack.enter_context(patch.object(psycopg, "connect", forbidden))
            # Override settings only; real tools remain intact and serving .env is ignored.
            for module in list(sys.modules.values()):
                name = getattr(module, "__name__", "")
                if name.startswith(
                    (
                        "agents.",
                        "app.",
                        "retrieval.",
                        "governance.",
                        "memory.",
                        "observability.",
                    )
                ) and hasattr(module, "get_settings"):
                    stack.enter_context(patch.object(module, "get_settings", return_value=settings))
            for partition, query, filters, expected in cases:
                vectors = store.query(embedder.embed([query])[0], 30, filters=filters)
                hits = hybrid.hybrid_search(query, store=store, embedder=embedder, filters=filters)
                expected_source = (
                    {
                        review_parent_id(row)[0]
                        for row in rows
                        if row["asin"] in filters.get("asin", [])
                    }
                    if expected
                    else set()
                )
                expected_indexed = expected_source & store.parents.keys()
                returned = {h.chunk.parent_id for h in hits}
                keywords = store.keyword_query(lexical_query(query), 30, filters=filters)
                vector_parents = {h.chunk.parent_id for h in vectors[: settings.retrieval_top_k]}
                keyword_parents = {h.chunk.parent_id for h in keywords}
                report["retrieval"].append(
                    {
                        "partition": partition,
                        "query": query,
                        "expected_nonempty": expected,
                        "raw_scores": [round(h.score, 4) for h in vectors],
                        "returned_parents": [h.chunk.parent_id for h in hits],
                        "assessment": hits.assessment,
                        "expected_source_parents": sorted(expected_source),
                        "expected_indexed_parents": sorted(expected_indexed),
                        "indexed_parent_recall": (
                            len(returned & expected_indexed) / len(expected_indexed)
                            if expected_indexed
                            else None
                        ),
                        "source_parent_recall": (
                            len(returned & expected_source) / len(expected_source)
                            if expected_source
                            else None
                        ),
                        "lexical_relevant_parents": len(keyword_parents & expected_source),
                        "lexical_only_relevant_parents": len(
                            (keyword_parents - vector_parents) & expected_source
                        ),
                    }
                )
                check(
                    query,
                    (
                        bool(hits) == expected
                        and (not expected_indexed or expected_indexed <= returned)
                    ),
                )
            for filters in ({"category": []}, {"category": ["Books"], "asin": ["P1"]}):
                check(
                    "empty/crossed scope",
                    not hybrid.hybrid_search(
                        "battery", filters=filters, store=store, embedder=embedder
                    ),
                )
            output.write_text(json.dumps(report, indent=2) + "\n")
            pointer = workspace / "current.json"
            write_fixture_pointer(pointer, first)
            settings.evidence_bundle_path = str(pointer)
            answer = await pipeline.answer(
                "Why are our lowest-rated electronics disappointing customers "
                "using lowest average ratings with at least 2 reviews, show 1?",
                "marketing",
            )
            check(
                "pipeline selection and constrained retrieval tools",
                answer.audit["tool_path"] == ["sql_agent", "review_rag"] and bool(answer.citations),
            )
            check(
                "no hosted generation",
                answer.audit["cost_usd"] == 0 and not answer.audit["llm_calls"],
            )
            check(
                "SQL selection independent of chunk counts",
                answer.sql is not None
                and answer.sql.rows[0][0] == "P1"
                and answer.sql.rows[0][-1] == 2,
            )
            report["product_pipeline"] = {
                "evidence": answer.audit.get("evidence"),
                "grounding": answer.audit.get("grounding"),
                "citation_count": len(answer.citations),
            }
            check(
                "honest selection-only when generic query is below relevance floor",
                answer.audit.get("evidence", {}).get("status") == "none"
                and answer.audit.get("grounding", {}).get("path") == "selection_only",
            )
            targeted = await pipeline.answer(
                "Why do customers complain about battery charging in Electronics?",
                "marketing",
            )
            check(
                "real pipeline retrieves relevant review evidence",
                bool(targeted.citations)
                and targeted.audit.get("evidence", {}).get("status") == "available",
            )
            check(
                "scope enforced in candidate pipeline",
                answer.audit["query_filters"]["category"] == ["Electronics"],
            )
            denied = await pipeline.answer("What do customers say about Books?", "marketing")
            check("denied category has no evidence", not denied.citations)
            revised = [p for p in parents if p.parent_id != parents[0].parent_id]
            edit = revised[0].model_copy(
                update={
                    "text": "Replacement battery works now.",
                    "content_hash": content_hash("Replacement battery works now."),
                    "source_hash": content_hash("Replacement battery works now."),
                    "source_snapshot": "fixture:stage3-v2",
                }
            )
            revised[0] = edit
            second = workspace / "v2"
            report["reconcile"] = build_fixture_bundle(
                second,
                version="v2",
                parents=revised,
                structured_rows=structured,
                embedder=embedder,
                seed="stage3-frozen",
                previous=store,
            )
            write_fixture_pointer(pointer, second)
            check(
                "atomic switch binds SQL and index",
                open_bundle(pointer).manifest.corpus_version == "v2"
                and sql_agent.gold_structured_path() == (second / "gold" / "structured").resolve(),
            )
            check(
                "deleted docs removed",
                not open_bundle(pointer).keyword_query(
                    "damaged", 5, filters={"source_type": "doc"}
                ),
            )
            write_fixture_pointer(pointer, first)
            check(
                "rollback restores prior doc evidence",
                bool(
                    open_bundle(pointer).keyword_query("damaged", 5, filters={"source_type": "doc"})
                ),
            )
    report["limitations"] = [
        "Synthetic sources only; no serving backfill or quality improvement claimed.",
        "Two calibration and four held-out probes are too small for general relevance calibration.",
        "No hosted synthesis, browser, or factual-support score is measured.",
    ]
    report["passed"] = all(c["status"] == "PASS" for c in report["checks"])
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(run(args.output))
    print(json.dumps({"passed": report["passed"], "checks": report["checks"], "hosted_usd": 0}))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
