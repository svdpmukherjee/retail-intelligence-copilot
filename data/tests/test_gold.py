import json
import shutil
from pathlib import Path

import pytest
from app.config import Settings
from data.etl.bronze import default_source_path
from data.etl.pipeline import run_pipeline
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path


def _build_lake(root, **overrides):
    real = Path(default_source_path(Settings(etl_runtime="local", _env_file=None)))
    settings = Settings(
        etl_runtime="local",
        data_lake_path=str(root),
        pii_hash_salt="test-salt",
        _env_file=None,
        **overrides,
    )
    # run_pipeline reads the sample from <lake>/sample, so stage it in the temp lake.
    Path(default_source_path(settings)).parent.mkdir(parents=True)
    shutil.copy(real, default_source_path(settings))
    manifest = run_pipeline(settings)
    return settings, manifest, get_spark(settings)


@pytest.fixture(scope="module")
def lake(tmp_path_factory):
    return _build_lake(tmp_path_factory.mktemp("lake"))


@pytest.fixture(scope="module")
def capped_lakes(tmp_path_factory):
    caps = {"sql_rows_per_category": 2, "rag_rows_per_category": 2}
    return [_build_lake(tmp_path_factory.mktemp(f"capped{i}"), **caps) for i in (1, 2)]


def _read(spark, settings, name):
    return spark.read.format("delta").load(str(Path(resolve_layer_path("gold", settings)) / name))


def _cats(df):
    return {r["category"] for r in df.select("category").distinct().collect()}


def test_gold_tables_are_filtered_and_split_by_purpose(lake):
    settings, _, spark = lake
    structured, reviews = _read(spark, settings, "structured"), _read(spark, settings, "reviews")
    assert structured.count() > 0 and reviews.count() > 0
    assert _cats(structured) <= set(settings.sql_categories)
    assert _cats(reviews) <= set(settings.rag_categories)
    assert {"asin", "user_id_hash", "year", "rating", "category"} <= set(structured.columns)
    assert "text" not in structured.columns
    assert not {"user_id", "user_id_hash", "name"} & set(reviews.columns)
    assert {"asin", "text", "category"} <= set(reviews.columns)


def test_manifest_counts_match_real_tables(lake):
    settings, returned, spark = lake
    gold = Path(resolve_layer_path("gold", settings))
    manifest = json.loads((gold / "_manifest.json").read_text())
    assert manifest == returned
    rc = manifest["row_counts"]
    for key, layer in (("bronze", "bronze"), ("silver", "silver")):
        real = spark.read.format("delta").load(resolve_layer_path(layer, settings)).count()
        assert rc[key] == real
    assert rc["gold_structured"] == _read(spark, settings, "structured").count()
    assert rc["gold_reviews"] == _read(spark, settings, "reviews").count()
    assert manifest["run_timestamp"]
    assert (manifest["year_min"], manifest["year_max"]) == (
        settings.etl_year_min,
        settings.etl_year_max,
    )
    assert manifest["sql_categories"] == settings.sql_categories
    assert manifest["rag_categories"] == settings.rag_categories


def test_run_pipeline_produces_all_layers(lake):
    settings, _, _ = lake
    for layer in ("bronze", "silver"):
        assert (Path(resolve_layer_path(layer, settings)) / "_delta_log").exists()
    gold = Path(resolve_layer_path("gold", settings))
    for name in ("structured", "reviews"):
        assert (gold / name / "_delta_log").exists()
    assert (gold / "_manifest.json").exists()


def test_default_categories_are_the_same_fifteen_and_independent():
    s = Settings(_env_file=None)
    assert len(s.sql_categories) == 15 and s.sql_categories == s.rag_categories
    assert (s.sql_rows_per_category, s.rag_rows_per_category) == (100000, 15000)
    s2 = Settings(_env_file=None, sql_categories=["Books"], rag_categories=["Toys_and_Games"])
    assert s2.sql_categories != s2.rag_categories


def test_manifest_has_caps_and_per_category_counts_matching_tables(lake):
    settings, manifest, spark = lake
    assert manifest["sql_rows_per_category"] == 100000
    assert manifest["rag_rows_per_category"] == 15000
    for name in ("structured", "reviews"):
        df = _read(spark, settings, name)
        real = {r["category"]: r["count"] for r in df.groupBy("category").count().collect()}
        assert manifest[f"gold_{name}_by_category"] == real
        assert sum(real.values()) == manifest["row_counts"][f"gold_{name}"]


def test_default_caps_leave_sample_uncapped(lake):
    settings, manifest, spark = lake
    silver = spark.read.format("delta").load(resolve_layer_path("silver", settings))
    in_scope = silver.filter(silver.category.isin(settings.sql_categories)).count()
    assert manifest["row_counts"]["gold_structured"] == in_scope


def test_cap_is_enforced_per_category_and_deterministic(capped_lakes):
    (s1, m1, spark), (s2, m2, _) = capped_lakes
    assert m1["sql_rows_per_category"] == m1["rag_rows_per_category"] == 2
    for name in ("structured", "reviews"):
        counts = m1[f"gold_{name}_by_category"]
        assert counts and max(counts.values()) <= 2
        assert m2[f"gold_{name}_by_category"] == counts
        a = _read(spark, s1, name).collect()
        b = _read(spark, s2, name).collect()
        assert sorted(map(str, a)) == sorted(map(str, b))
