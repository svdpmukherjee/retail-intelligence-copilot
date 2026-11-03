"""Tiny isolated Silver→Gold integration; uses only explicit cached Delta jars."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.config import Settings
from data.etl.gold import run_gold
from pyspark.sql import SparkSession


@pytest.fixture(scope="module")
def spark():
    jars = os.environ.get("STAGE3_DELTA_JARS")
    if not jars or not all(Path(path).is_file() for path in jars.split(",")):
        pytest.skip("STAGE3_DELTA_JARS must point to existing cached Delta jars; no downloads")
    previous_python = os.environ.get("PYSPARK_PYTHON")
    os.environ["PYSPARK_PYTHON"] = sys.executable
    session = (
        SparkSession.builder.master("local[1]")
        .appName("stage3-isolated-gold")
        .config("spark.jars", jars)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )
    yield session
    session.stop()
    if previous_python is None:
        os.environ.pop("PYSPARK_PYTHON", None)
    else:
        os.environ["PYSPARK_PYTHON"] = previous_python


def test_metadata_identity_and_snapshot_survive_projection_and_text_edit(spark, tmp_path):
    settings = Settings(
        _env_file=None,
        data_lake_path=str(tmp_path),
        sql_categories=["Electronics"],
        rag_categories=["Electronics"],
        sql_rows_per_category=10,
        rag_rows_per_category=10,
        etl_storage="local",
    )
    rows = [
        dict(
            asin="P",
            category="Electronics",
            user_id_hash=f"private-fixture-{i}",
            review_id="upstream-one" if i == 0 else None,
            timestamp=datetime(2023, 1, 1, tzinfo=UTC),
            year=2023,
            rating=float(i + 1),
            product_title="Device",
            title="Review",
            text="equal text",
        )
        for i in range(2)
    ]
    frame = spark.createDataFrame(rows)
    for layer in ("silver", "bronze"):
        frame.write.format("delta").save(str(tmp_path / layer))
    first = run_gold(spark, settings)
    reviews = spark.read.format("delta").load(str(tmp_path / "gold" / "reviews")).collect()
    structured = spark.read.format("delta").load(str(tmp_path / "gold" / "structured")).collect()
    assert len(reviews) == 2 and len({r.parent_id for r in reviews}) == 2
    assert {r.parent_id for r in reviews} == {r.parent_id for r in structured}
    assert all(r.rating and r.timestamp and r.product_title == "Device" for r in reviews)
    assert all(r.source_snapshot == "silver:0" for r in reviews)
    assert {r.identity_kind for r in reviews} == {
        "silver_upstream_id_v1",
        "silver_source_tuple_v1",
    }
    assert not {"user_id_hash", "review_id", "user_id"} & set(reviews[0].asDict())
    ids = {r.parent_id for r in reviews}
    updated = [{**row, "text": "Edited text with correction"} for row in rows]
    spark.createDataFrame(updated).write.format("delta").mode("overwrite").save(
        str(tmp_path / "silver")
    )
    second = run_gold(spark, settings)
    refreshed = spark.read.format("delta").load(str(tmp_path / "gold" / "reviews")).collect()
    assert {r.parent_id for r in refreshed} == ids
    assert all(r.text == "Edited text with correction" for r in refreshed)
    assert first["source_snapshot"] == "silver:0" and second["source_snapshot"] == "silver:1"
