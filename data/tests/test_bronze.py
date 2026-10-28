import json
from pathlib import Path

import pytest
from app.config import Settings
from data.etl.bronze import default_source_path, run_bronze
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path


@pytest.fixture(scope="module")
def spark():
    return get_spark(Settings(etl_runtime="local", _env_file=None))


def test_bronze_lands_sample_with_provenance_and_all_fields(spark, tmp_path):
    settings = Settings(etl_runtime="local", data_lake_path=str(tmp_path), _env_file=None)
    source = default_source_path(Settings(etl_runtime="local", _env_file=None))
    rows = [json.loads(line) for line in Path(source).read_text().splitlines() if line]

    run_bronze(spark, source_path=source, settings=settings)
    bronze = spark.read.format("delta").load(resolve_layer_path("bronze", settings))

    assert bronze.count() == len(rows) == 40
    assert {"_ingested_at", "_source"} <= set(bronze.columns)
    assert set(rows[0]) <= set(bronze.columns)
    first = bronze.where("user_id = 'USER0000'").first()
    assert first["text"] == rows[0]["text"]
    assert first["rating"] == rows[0]["rating"]
    assert first["_source"] == source
