import pytest
from app.config import Settings
from data.etl.storage import blob_enabled, publish_gold_to_blob, resolve_layer_path


def test_local_storage_resolves_under_data_lake_path():
    settings = Settings(etl_storage="local", data_lake_path="lake", _env_file=None)
    assert resolve_layer_path("bronze", settings) == "lake/bronze"
    assert resolve_layer_path("gold", settings) == "lake/gold"


def test_compute_is_always_local_even_in_blob_mode():
    # ETL_STORAGE=blob does not change where Spark writes (it publishes Gold afterward),
    # so layer paths stay local and no longer raise.
    settings = Settings(etl_storage="blob", data_lake_path="lake", _env_file=None)
    assert resolve_layer_path("silver", settings) == "lake/silver"
    assert blob_enabled(settings) is True
    assert blob_enabled(Settings(etl_storage="local", _env_file=None)) is False


def test_publish_gold_fails_loud_without_blob_config(tmp_path):
    settings = Settings(etl_storage="blob", _env_file=None)  # no connection string
    with pytest.raises(ValueError, match="AZURE_BLOB_CONNECTION_STRING"):
        publish_gold_to_blob(tmp_path, settings)


def test_category_lists_split_from_csv():
    settings = Settings(sql_categories="A, B,C", rag_categories="A", _env_file=None)
    assert settings.sql_categories == ["A", "B", "C"]
    assert settings.rag_categories == ["A"]
