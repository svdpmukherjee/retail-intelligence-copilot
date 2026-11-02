from app.config import Settings, get_settings
from data.etl.bronze import run_bronze
from data.etl.gold import run_gold
from data.etl.product_meta import run_product_meta
from data.etl.silver import run_silver
from data.etl.spark_session import get_spark


def run_pipeline(settings: Settings | None = None) -> dict:
    """Chain Bronze -> Product dim -> Silver -> Gold; Gold writes the returned manifest.

    The product dimension (item metadata) is built before Silver so Silver can join real
    price/title/rating onto each review; it is a no-op when no metadata is present.
    """
    settings = settings or get_settings()
    spark = get_spark(settings)
    run_bronze(spark, settings=settings)
    run_product_meta(spark, settings)
    run_silver(spark, settings)
    return run_gold(spark, settings)


if __name__ == "__main__":
    run_pipeline()
