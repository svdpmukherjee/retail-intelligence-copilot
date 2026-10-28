import asyncio

import pytest
from deltalake import DeltaTable

from agents import sql_agent as mod
from agents.sql_agent import (
    SQLComputeError,
    SQLGenerationUnavailable,
    UnsafeSQLError,
    _safe_select,
    run_sql,
    sql_agent,
)
from app.cost import CostLedger


def test_safe_select_accepts_single_select():
    assert _safe_select("SELECT count(*) FROM structured;") == "SELECT count(*) FROM structured"


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE structured",
        "SELECT 1; DROP TABLE structured",
        "DELETE FROM structured",
        "INSERT INTO structured VALUES (1)",
        "UPDATE structured SET rating = 5",
        "CREATE TABLE x AS SELECT 1",
        "ATTACH 'x.db'",
        "COPY structured TO 'x.csv'",
        "PRAGMA database_list",
        "SELECT * FROM read_csv('x.csv')",
        "",
    ],
)
def test_safe_select_rejects_unsafe(sql):
    with pytest.raises(UnsafeSQLError):
        _safe_select(sql)


def test_run_sql_blocks_unsafe_before_executing():
    with pytest.raises(UnsafeSQLError):
        run_sql("SELECT 1; DROP TABLE structured")


def test_aggregate_over_committed_gold_is_exact():
    table = DeltaTable(str(mod.gold_structured_path())).to_pyarrow_table()
    ratings = table.column("rating").to_pylist()
    out = run_sql("SELECT count(*) AS n, sum(rating) AS total FROM structured")
    assert out["columns"] == ["n", "total"]
    assert out["rows"] == [[len(ratings), sum(ratings)]]


def test_scope_category_limits_rows():
    table = DeltaTable(str(mod.gold_structured_path())).to_pyarrow_table()
    category = table.column("category").to_pylist()[0]
    expected = table.column("category").to_pylist().count(category)
    out = run_sql("SELECT count(*) FROM structured", {"category": category})
    assert out["rows"] == [[expected]]


def test_generation_refuses_cleanly_without_llm(monkeypatch):
    monkeypatch.setattr(mod, "get_llm", lambda: type("L", (), {"available": False})())
    with pytest.raises(SQLGenerationUnavailable, match="needs an LLM"):
        asyncio.run(sql_agent("average rating?", None, CostLedger()))


def test_sql_agent_runs_generated_sql_through_guard(monkeypatch):
    class FakeLLM:
        available = True

        async def complete(self, system, user, *, ledger, max_tokens=None):
            return "```sql\nSELECT count(*) AS n FROM structured\n```"

    monkeypatch.setattr(mod, "get_llm", lambda: FakeLLM())
    out = asyncio.run(sql_agent("how many rows?", None, CostLedger()))
    assert out["columns"] == ["n"] and out["sql"] == "SELECT count(*) AS n FROM structured"


def test_safe_select_requires_from():
    with pytest.raises(UnsafeSQLError, match="FROM"):
        _safe_select("SELECT price")
    assert _safe_select("SELECT count(*) FROM structured") == "SELECT count(*) FROM structured"


def _scripted_llm(monkeypatch, replies):
    calls = []

    class FakeLLM:
        available = True

        async def complete(self, system, user, *, ledger, max_tokens=None):
            calls.append(user)
            return replies[len(calls) - 1]

    monkeypatch.setattr(mod, "get_llm", lambda: FakeLLM())
    return calls


@pytest.mark.parametrize("bad", ["SELECT price", "SELECT no_such_col FROM structured"])
def test_sql_agent_retries_once_then_succeeds(monkeypatch, bad):
    calls = _scripted_llm(monkeypatch, [bad, "SELECT count(*) AS n FROM structured"])
    out = asyncio.run(sql_agent("how many rows?", None, CostLedger()))
    assert out["columns"] == ["n"] and len(calls) == 2


def test_sql_agent_raises_clean_error_after_second_failure(monkeypatch):
    calls = _scripted_llm(monkeypatch, ["SELECT price", "SELECT no_such_col FROM structured"])
    with pytest.raises(SQLComputeError) as exc_info:
        asyncio.run(sql_agent("how many rows?", None, CostLedger()))
    assert len(calls) == 2 and "Binder" not in str(exc_info.value)
