import json
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings, get_settings
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

STRUCTURED_COLUMNS = (
    "asin",
    "user_id_hash",
    "year",
    "rating",
    "price",
    "category",
    "verified_purchase",
    "timestamp",
    "helpful_vote",
)
# Only redacted free text plus metadata; no reviewer identifiers reach the RAG index.
REVIEW_TEXT_COLUMNS = ("asin", "title", "text", "description", "category", "year")
MANIFEST_FILE = "_manifest.json"


def _select_present(df: DataFrame, columns: tuple[str, ...]) -> DataFrame:
    return df.select(*[c for c in columns if c in df.columns])


def _cap_per_category(df: DataFrame, cap: int) -> DataFrame:
    # Total order (timestamp desc, asin asc, then reviewer hash for same-asin ties) keeps the
    # selected rows identical across re-runs.
    order = Window.partitionBy("category").orderBy(
        F.col("timestamp").desc(), F.col("asin").asc(), F.col("user_id_hash").asc()
    )
    return df.withColumn("_rn", F.row_number().over(order)).filter(F.col("_rn") <= cap).drop("_rn")


def _by_category(df: DataFrame) -> dict[str, int]:
    return {r["category"]: r["count"] for r in df.groupBy("category").count().collect()}


def run_gold(spark: SparkSession, settings: Settings | None = None) -> dict:
    """Split Silver into the SQL and RAG Gold tables and write a manifest."""
    settings = settings or get_settings()
    gold_root = Path(resolve_layer_path("gold", settings))
    silver = spark.read.format("delta").load(resolve_layer_path("silver", settings))

    # Cap before projecting so the ordering columns (timestamp) are still present.
    tables = {
        "structured": _select_present(
            _cap_per_category(
                silver.filter(F.col("category").isin(settings.sql_categories)),
                settings.sql_rows_per_category,
            ),
            STRUCTURED_COLUMNS,
        ),
        "reviews": _select_present(
            _cap_per_category(
                silver.filter(F.col("category").isin(settings.rag_categories)),
                settings.rag_rows_per_category,
            ),
            REVIEW_TEXT_COLUMNS,
        ),
    }
    by_category = {}
    counts = {
        "bronze": spark.read.format("delta").load(resolve_layer_path("bronze", settings)).count(),
        "silver": silver.count(),
    }
    for name, df in tables.items():
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
            str(gold_root / name)
        )
        counts[f"gold_{name}"] = df.count()
        by_category[f"gold_{name}_by_category"] = _by_category(
            spark.read.format("delta").load(str(gold_root / name))
        )

    manifest = {
        "run_timestamp": datetime.now(UTC).isoformat(),
        "row_counts": counts,
        "year_min": settings.etl_year_min,
        "year_max": settings.etl_year_max,
        "sql_categories": settings.sql_categories,
        "rag_categories": settings.rag_categories,
        "sql_rows_per_category": settings.sql_rows_per_category,
        "rag_rows_per_category": settings.rag_rows_per_category,
        **by_category,
    }
    gold_root.mkdir(parents=True, exist_ok=True)
    (gold_root / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    run_gold(get_spark())
