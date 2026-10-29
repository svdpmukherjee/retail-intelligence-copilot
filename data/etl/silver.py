from app.config import Settings, get_settings
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path
from governance.pii import EMAIL_PATTERN, PHONE_PATTERN
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

TEXT_COLUMNS = ("title", "text")
KEY_COLUMNS = ("asin", "user_id_hash", "timestamp")


def redact_pii(df: DataFrame, settings: Settings | None = None) -> DataFrame:
    """The single PII enforcement point: hash user id, drop name, scrub free text."""
    settings = settings or get_settings()
    if settings.pii_hash_salt is None:
        raise ValueError("PII_HASH_SALT must be set; refusing to write Silver without it.")
    salt = settings.pii_hash_salt.get_secret_value()
    out = df.withColumn(
        "user_id_hash",
        F.sha2(F.concat(F.lit(salt), F.col("user_id").cast("string")), 256),
    ).drop("user_id", "name")
    for col in TEXT_COLUMNS:
        out = out.withColumn(
            col,
            F.regexp_replace(
                F.regexp_replace(col, EMAIL_PATTERN, "[EMAIL]"),
                PHONE_PATTERN,
                "[PHONE]",
            ),
        )
    return out


def run_silver(spark: SparkSession, settings: Settings | None = None) -> DataFrame:
    """Type, drop malformed rows, window-filter, redact PII, dedup; write Silver Delta."""
    settings = settings or get_settings()
    bronze = spark.read.format("delta").load(resolve_layer_path("bronze", settings))
    # The real review feed has no `price` (it lives in the item-metadata feed, not here);
    # add it as a null float so the cast below works for both the sample and the real corpus.
    if "price" not in bronze.columns:
        bronze = bronze.withColumn("price", F.lit(None).cast("float"))
    # Casts yield null on unparseable values; those rows are dropped below, not defaulted.
    typed = (
        bronze.withColumn("rating", F.col("rating").cast("float"))
        .withColumn("price", F.col("price").cast("float"))
        .withColumn("category", F.col("category").cast("string"))
        .withColumn("verified_purchase", F.col("verified_purchase").cast("boolean"))
        # Source timestamps are epoch milliseconds.
        .withColumn("timestamp", (F.col("timestamp").cast("long") / 1000).cast("timestamp"))
        .withColumn("year", F.year("timestamp"))
    )
    clean = typed.dropna(subset=["asin", "user_id", "rating", "timestamp"]).filter(
        F.col("year").between(settings.etl_year_min, settings.etl_year_max)
    )
    silver = redact_pii(clean, settings).dropDuplicates(list(KEY_COLUMNS))
    silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(
        resolve_layer_path("silver", settings)
    )
    return silver


if __name__ == "__main__":
    run_silver(get_spark())
