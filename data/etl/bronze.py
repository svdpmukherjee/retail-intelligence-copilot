from pathlib import Path

from app.config import Settings, get_settings
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

SAMPLE_FILE = "amazon_reviews_sample.jsonl"
# The real corpus is one JSONL per category under <lake>/raw/; the category is the
# file stem (the review feed itself carries no category column).
RAW_GLOB = "*.jsonl"
_CATEGORY_FROM_FILE = r".*/([^/]+)\.jsonl$"


def default_source_path(settings: Settings) -> str:
    """The committed sample; the full corpus lives under <lake>/raw/ (see raw_source_glob)."""
    return str(Path(settings.data_lake_path) / "sample" / SAMPLE_FILE)


def raw_source_glob(settings: Settings) -> str:
    """Glob for the real multi-category corpus (one JSONL per category)."""
    return str(Path(settings.data_lake_path) / "raw" / RAW_GLOB)


def _has_raw_corpus(settings: Settings) -> bool:
    raw_dir = Path(settings.data_lake_path) / "raw"
    return raw_dir.is_dir() and any(raw_dir.glob(RAW_GLOB))


def run_bronze(
    spark: SparkSession,
    source_path: str | None = None,
    settings: Settings | None = None,
) -> DataFrame:
    """Land raw JSONL into Bronze Delta as-is, adding only provenance (and category) columns.

    With no explicit source_path, read the real `<lake>/raw/*.jsonl` corpus if present
    (per-file provenance via input_file_name), else fall back to the committed sample.
    """
    settings = settings or get_settings()
    if settings.etl_runtime == "databricks":
        raise NotImplementedError(
            "ETL_RUNTIME=databricks requires explicit human go-ahead (cloud spend); "
            "the Databricks serverless submission path is a documented, gated seam, "
            "not wired locally. Use ETL_RUNTIME=local (Spark); see P3_etl_spec.md."
        )
    multi_file = source_path is None and _has_raw_corpus(settings)
    source = source_path or (
        raw_source_glob(settings) if multi_file else default_source_path(settings)
    )
    df = spark.read.json(source).withColumn("_ingested_at", F.current_timestamp())
    # Per-file provenance for a glob read; a single explicit source keeps its literal path.
    df = df.withColumn("_source", F.input_file_name() if multi_file else F.lit(source))
    # The real feed has no category column; derive it from the file name. The sample
    # already carries one, so only fill it when absent.
    if "category" not in df.columns:
        df = df.withColumn(
            "category", F.regexp_extract(F.input_file_name(), _CATEGORY_FROM_FILE, 1)
        )
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        resolve_layer_path("bronze", settings)
    )
    return df


if __name__ == "__main__":
    run_bronze(get_spark())
