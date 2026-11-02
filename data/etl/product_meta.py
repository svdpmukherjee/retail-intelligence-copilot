import glob
from pathlib import Path

from app.config import Settings, get_settings
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# One row per product (keyed by `parent_asin`); the item attributes the review feed
# lacks. Price/name/avg-rating live only in Amazon's item-metadata feed, so this is the
# single place they enter the lake (see data-pipeline-setup/local/LOCAL_SETUP.md § B.6).
PRODUCT_COLUMNS = (
    "parent_asin",
    "product_title",
    "product_price",
    "product_avg_rating",
    "product_rating_count",
    "store",
    "main_category",
)


def raw_meta_glob(settings: Settings) -> str:
    """Filtered item-metadata JSONL (one file per category) under `<lake>/raw_meta/`."""
    return str(Path(settings.data_lake_path) / "raw_meta" / "meta_*.jsonl")


def has_product_meta(settings: Settings) -> bool:
    """True when at least one filtered metadata file is present (absent for the sample)."""
    return bool(glob.glob(raw_meta_glob(settings)))


def run_product_meta(spark: SparkSession, settings: Settings | None = None) -> DataFrame | None:
    """Build the product dimension Delta from `<lake>/raw_meta/`; no-op when absent.

    Returns None when no metadata is present (e.g. the committed sample), so the Silver
    enrichment join is simply skipped and the sample pipeline is unchanged.
    """
    settings = settings or get_settings()
    if not has_product_meta(settings):
        return None
    raw = spark.read.json(raw_meta_glob(settings))
    typed = (
        raw.withColumn("product_price", F.col("price").cast("float"))
        .withColumn("product_avg_rating", F.col("product_avg_rating").cast("float"))
        .withColumn("product_rating_count", F.col("product_rating_count").cast("long"))
    )
    # One row per product: keep the record with the most ratings on a duplicate parent_asin.
    order = Window.partitionBy("parent_asin").orderBy(
        F.col("product_rating_count").desc_nulls_last()
    )
    deduped = (
        typed.filter(F.col("parent_asin").isNotNull())
        .withColumn("_rn", F.row_number().over(order))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )
    product = deduped.select(*PRODUCT_COLUMNS)
    product.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        resolve_layer_path("product", settings)
    )
    return product


if __name__ == "__main__":
    run_product_meta(get_spark())
