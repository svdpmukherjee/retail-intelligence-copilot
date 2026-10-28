from pathlib import Path

from app.config import Settings, get_settings
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

SAMPLE_FILE = "amazon_reviews_sample.jsonl"


def default_source_path(settings: Settings) -> str:
    """The committed sample; the full HF/Databricks source stays behind etl_runtime."""
    return str(Path(settings.data_lake_path) / "sample" / SAMPLE_FILE)


def run_bronze(
    spark: SparkSession, source_path: str | None = None, settings: Settings | None = None
) -> DataFrame:
    """Land raw JSONL into Bronze Delta as-is, adding only provenance columns."""
    settings = settings or get_settings()
    if settings.etl_runtime == "databricks":
        raise NotImplementedError(
            "ETL_RUNTIME=databricks requires explicit human go-ahead (cloud spend); "
            "the full-source read is not enabled locally."
        )
    source = source_path or default_source_path(settings)
    df = (
        spark.read.json(source)
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source", F.lit(source))
    )
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        resolve_layer_path("bronze", settings)
    )
    return df


if __name__ == "__main__":
    run_bronze(get_spark())
