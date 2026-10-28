import json
import re
from pathlib import Path

import pytest
from app.config import Settings
from data.etl.bronze import default_source_path, run_bronze
from data.etl.silver import redact_pii, run_silver
from data.etl.spark_session import get_spark
from data.etl.storage import resolve_layer_path
from pyspark.sql.types import BooleanType, FloatType, IntegerType, StringType, TimestampType

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}|\b\d{3}[\s.\-]\d{4}\b")
PHONE_TEXTS = [
    "Call (555) 019-2345 now",
    "Call 555.019.2345 now",
    "Call 555-019-2345 now",
    "Call +1 555 019 2345 now",
    "Call 5550192345 now",
]
TS_2021 = 1609459200000 + 86400000


@pytest.fixture(scope="module")
def spark():
    return get_spark(Settings(etl_runtime="local", _env_file=None))


def _settings(tmp_path, salt="test-salt"):
    return Settings(
        etl_runtime="local", data_lake_path=str(tmp_path), pii_hash_salt=salt, _env_file=None
    )


@pytest.fixture
def silver(spark, tmp_path):
    settings = _settings(tmp_path)
    sample = Path(default_source_path(Settings(etl_runtime="local", _env_file=None)))
    rows = [json.loads(line) for line in sample.read_text().splitlines() if line]
    base = dict(rows[0], timestamp=TS_2021)
    extra = [
        dict(base, user_id=f"PH{i}", name=f"Ph {i}", asin=f"PHX{i}", text=t)
        for i, t in enumerate(PHONE_TEXTS)
    ]
    extra.append(dict(base, user_id="DUP", asin="DUPX", name="Dup"))
    extra.append(dict(base, user_id="DUP", asin="DUPX", name="Dup"))
    extra.append(dict(base, user_id="NOASIN", asin=None))
    src = tmp_path / "input.jsonl"
    src.write_text("\n".join(json.dumps(r) for r in rows + extra))
    run_bronze(spark, source_path=str(src), settings=settings)
    run_silver(spark, settings)
    df = spark.read.format("delta").load(resolve_layer_path("silver", settings))
    return df, rows


def test_silver_types_dedups_and_drops_malformed(silver):
    df, _ = silver
    types = {f.name: f.dataType for f in df.schema.fields}
    assert isinstance(types["rating"], FloatType)
    assert isinstance(types["price"], FloatType)
    assert isinstance(types["category"], StringType)
    assert isinstance(types["verified_purchase"], BooleanType)
    assert isinstance(types["timestamp"], TimestampType)
    assert isinstance(types["year"], IntegerType)
    key = ["asin", "user_id_hash", "timestamp"]
    assert df.count() == df.dropDuplicates(key).count()
    assert df.where("user_id_hash is null or asin is null").count() == 0
    assert df.where("asin = 'DUPX'").count() == 1


def test_silver_window_filter_drops_out_of_range_years(silver):
    df, rows = silver
    years = {r["year"] for r in df.select("year").collect()}
    assert min(years) >= 2019 and max(years) <= 2023
    assert any(r["timestamp"] < 1546300800000 or r["timestamp"] >= 1704067200000 for r in rows)
    assert df.count() < len(rows)


def test_silver_has_no_raw_pii_in_any_string_column(silver):
    df, _ = silver
    assert "user_id_hash" in df.columns
    assert "user_id" not in df.columns and "name" not in df.columns
    string_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, StringType)]
    for row in df.select(*string_cols).collect():
        for col in string_cols:
            value = row[col] or ""
            assert not EMAIL.search(value), (col, value)
            if col != "user_id_hash":  # hex digest can contain digit runs
                assert not PHONE.search(value), (col, value)
            assert "USER0" not in value and "Test Reviewer" not in value, (col, value)
    texts = [r["text"] for r in df.where("asin like 'PHX%'").select("text").collect()]
    assert len(texts) == len(PHONE_TEXTS)
    assert all("[PHONE]" in t for t in texts), texts
    assert any("[EMAIL]" in (r["text"] or "") for r in df.select("text").collect())


def test_hash_depends_on_salt(spark, tmp_path):
    df = spark.sql(
        "select 'USER1' as user_id, 'Name' as name, 'a@b.test 555-0142' as text, 't' as title"
    )
    h1 = redact_pii(df, _settings(tmp_path, "salt-a")).first()["user_id_hash"]
    h2 = redact_pii(df, _settings(tmp_path, "salt-b")).first()["user_id_hash"]
    assert h1 != h2 and h1 != "USER1" and len(h1) == 64


def test_redact_pii_raises_without_salt(spark, tmp_path):
    df = spark.sql("select 'U' as user_id, 'N' as name, 'x' as text, 't' as title")
    with pytest.raises(ValueError, match="PII_HASH_SALT"):
        redact_pii(df, _settings(tmp_path, None))
