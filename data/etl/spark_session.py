from app.config import Settings, get_settings
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession


def get_spark(settings: Settings | None = None) -> SparkSession:
    """Local-mode SparkSession with Delta enabled; Databricks is gated until go-ahead."""
    settings = settings or get_settings()
    if settings.etl_runtime == "databricks":
        raise NotImplementedError(
            "ETL_RUNTIME=databricks requires explicit human go-ahead (cloud spend) and is "
            "not configured locally; use ETL_RUNTIME=local."
        )
    builder = (
        SparkSession.builder.master("local[2]")
        .appName("retail-intelligence-etl")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.ui.enabled", "false")
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()
