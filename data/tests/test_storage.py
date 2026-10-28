import pytest
from app.config import Settings
from data.etl.storage import resolve_layer_path


def test_local_storage_resolves_under_data_lake_path():
    settings = Settings(etl_storage="local", data_lake_path="lake", _env_file=None)
    assert resolve_layer_path("bronze", settings) == "lake/bronze"
    assert resolve_layer_path("gold", settings) == "lake/gold"


def test_blob_storage_raises_without_go_ahead():
    settings = Settings(etl_storage="blob", _env_file=None)
    with pytest.raises(NotImplementedError, match="human go-ahead"):
        resolve_layer_path("silver", settings)


def test_category_lists_split_from_csv():
    settings = Settings(sql_categories="A, B,C", rag_categories="A", _env_file=None)
    assert settings.sql_categories == ["A", "B", "C"]
    assert settings.rag_categories == ["A"]
