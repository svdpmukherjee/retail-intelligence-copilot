"""Read-only, snapshot-labelled SQL/Gold/index coverage; never reads review bodies."""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import psycopg
from deltalake import DeltaTable

from agents.sql_agent import gold_structured_path
from app.config import get_settings
from retrieval.index_reviews import gold_reviews_path

FIELDS = (
    "category",
    "asin",
    "parent_id",
    "rating",
    "timestamp",
    "product_title",
    "year",
)


def summarize(rows: Iterable[dict]) -> dict:
    """O(products + parents + strata) memory; count rows separately from distinct review parents."""
    products, strata, present = Counter(), Counter(), Counter()
    parents = set()
    count = missing_keys = duplicates = 0
    for row in rows:
        count += 1
        for field in FIELDS:
            if row.get(field) is not None:
                present[field] += 1
        category, asin = row.get("category"), row.get("asin")
        if category and asin:
            products[(category, asin)] += 1
        else:
            missing_keys += 1
        strata[(category, row.get("year"), row.get("rating"))] += 1
        # Stable review identity is unavailable in legacy Gold; do not infer from ASIN.
        if key := row.get("parent_id"):
            duplicates += key in parents
            parents.add(key)
    return {
        "rows": count,
        "products": products,
        "strata": strata,
        "non_null": {f: present[f] for f in FIELDS},
        "missing_product_keys": missing_keys,
        "unique_parents": len(parents) if present["parent_id"] == count else None,
        "duplicate_parent_rows": duplicates if present["parent_id"] == count else None,
    }


def compare(sql: dict, rag: dict, index: dict) -> dict:
    """Every ratio states its denominator; chunk coverage is not source review coverage."""
    s, r, i = (set(x["products"]) for x in (sql, rag, index))
    categories = sorted({cat for cat, _ in s | r | i})

    def metrics(a: set, b: set, c: set) -> dict:
        denom = sum(sql["products"][key] for key in a)
        numerator = sum(sql["products"][key] for key in a & c)
        return {
            "sql_products": len(a),
            "rag_products": len(b),
            "indexed_products": len(c),
            "triple_overlap": len(a & b & c),
            "sql_without_rag": len(a - b),
            "rag_without_sql": len(b - a),
            "sql_without_index": len(a - c),
            "index_without_sql": len(c - a),
            "rag_without_index": len(b - c),
            "index_without_rag": len(c - b),
            "sql_product_coverage": {"numerator": len(a & c), "denominator": len(a)},
            "sql_row_weighted_product_coverage": {
                "numerator": numerator,
                "denominator": denom,
            },
        }

    def serial(summary: dict) -> dict:
        return {
            **{k: v for k, v in summary.items() if k not in ("products", "strata")},
            "distinct_products": len(summary["products"]),
            "strata": [
                {"category": k[0], "year": k[1], "rating": k[2], "rows": n}
                for k, n in sorted(summary["strata"].items(), key=lambda x: str(x[0]))
            ],
        }

    return {
        "overall": metrics(s, r, i),
        "by_category": {
            cat: metrics(*({x for x in st if x[0] == cat} for st in (s, r, i)))
            for cat in categories
        },
        "layers": {name: serial(x) for name, x in [("sql", sql), ("rag", rag), ("index", index)]},
        "interpretation": "SQL-row-weighted coverage counts SQL rows whose product has at least "
        "one indexed chunk; it does not prove matching review coverage or relevant evidence.",
    }


def delta_snapshot(path: Path) -> tuple[dict, Iterable[dict]]:
    table = DeltaTable(str(path))
    version = table.version()
    dataset = DeltaTable(str(path), version=version).to_pyarrow_dataset()
    columns = [f for f in FIELDS if f in dataset.schema.names]

    def rows():
        for batch in dataset.to_batches(columns=columns, batch_size=8192):
            yield from batch.to_pylist()

    return {"delta_version": version, "available_fields": columns}, rows()


def audit(trace_asins: list[str]) -> dict:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL required for read-only coverage audit")
    sql_snapshot, sql_rows = delta_snapshot(gold_structured_path())
    rag_snapshot, rag_rows = delta_snapshot(gold_reviews_path())
    sql, rag = summarize(sql_rows), summarize(rag_rows)
    digest = hashlib.sha256()
    trace = {
        asin: {
            "sql_rows": sum(n for (_, a), n in sql["products"].items() if a == asin),
            "rag_rows": sum(n for (_, a), n in rag["products"].items() if a == asin),
        }
        for asin in trace_asins
    }
    with psycopg.connect(
        settings.database_url.get_secret_value(),
        connect_timeout=10,
        options="-c default_transaction_read_only=on -c statement_timeout=120000",
    ) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = conn.execute("SELECT pg_current_snapshot()::text").fetchone()[0]
        counts = dict(conn.execute("SELECT source_type, count(*) FROM chunks GROUP BY source_type"))

        def rows():
            with conn.cursor(name="coverage") as cur:
                cur.execute(
                    "SELECT id, category, asin, year FROM chunks "
                    "WHERE source_type='review' ORDER BY id"
                )
                for chunk_id, category, asin, year in cur:
                    digest.update(chunk_id.encode() + b"\n")
                    yield {"category": category, "asin": asin, "year": year}

        index = summarize(rows())
        for asin in trace:
            trace[asin]["indexed_chunks"] = sum(
                n for (_, a), n in index["products"].items() if a == asin
            )
        readonly = conn.execute("SHOW transaction_read_only").fetchone()[0]
    # Trace metadata only in existing local upstream layers. No ETL or downloads.
    import pyarrow.dataset as ds

    for layer in ("silver", "bronze"):
        path = gold_reviews_path().parents[1] / layer
        if not (path / "_delta_log").exists():
            for item in trace.values():
                item[layer] = {"status": "unavailable"}
            continue
        table = DeltaTable(str(path))
        version = table.version()
        dataset = DeltaTable(str(path), version=version).to_pyarrow_dataset()
        for asin, item in trace.items():
            item[layer] = {
                "delta_version": version,
                "rows": dataset.count_rows(filter=ds.field("asin") == asin),
                "available_fields": [f for f in FIELDS if f in dataset.schema.names],
            }
    return {
        **compare(sql, rag, index),
        "snapshots": {
            "sql": sql_snapshot,
            "rag": rag_snapshot,
            "index": {
                "transaction_snapshot": snapshot,
                "review_ids_sha256": digest.hexdigest(),
                "source_counts": counts,
                "read_only": readonly,
            },
        },
        "product_trace": trace,
        "limitations": [
            "Legacy index has no stable parent identity or rating/exact time/title.",
            "Cross-store snapshots are labelled independently, not atomically coordinated.",
            "No source text or reviewer identifiers were read into this report.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace-asin", action="append", default=[])
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if args.output.resolve().is_relative_to(repo):
        parser.error("Live coverage evidence must stay outside the repository")
    report = audit(args.trace_asin)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(
        json.dumps(
            {
                "overall": report["overall"],
                "read_only": report["snapshots"]["index"]["read_only"],
            }
        )
    )


if __name__ == "__main__":
    main()
