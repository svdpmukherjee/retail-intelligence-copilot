from app.config import Settings, get_settings
from data.etl.bronze import run_bronze
from data.etl.gold import run_gold
from data.etl.silver import run_silver
from data.etl.spark_session import get_spark


def run_pipeline(settings: Settings | None = None) -> dict:
    """Chain Bronze -> Silver -> Gold; Gold writes the manifest, which is returned."""
    settings = settings or get_settings()
    spark = get_spark(settings)
    run_bronze(spark, settings=settings)
    run_silver(spark, settings)
    return run_gold(spark, settings)


if __name__ == "__main__":
    run_pipeline()
