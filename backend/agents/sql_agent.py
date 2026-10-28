import logging
import re
from pathlib import Path

import duckdb
from deltalake import DeltaTable

from agents.llm import get_llm
from app.config import get_settings
from app.cost import CostLedger
from retrieval.vector_store import Filters

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE = "structured"
MAX_ROWS = 200

# Anything that writes, changes settings, or reaches outside the in-memory table.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|copy|pragma|install|load|call|set"
    r"|export|import|truncate|replace|merge|grant|read_\w+|glob|exec\w*)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = (
    "You write one DuckDB SQL SELECT statement answering the user's question over the table "
    "`{table}` with columns: {columns}. Return only the SQL, no prose, no markdown fences."
)


class UnsafeSQLError(ValueError):
    """The SQL is not a single read-only SELECT; it was not executed."""


class SQLComputeError(RuntimeError):
    """No valid, executable SQL was produced after retrying; message is safe to show."""


class SQLGenerationUnavailable(RuntimeError):
    """No LLM is available to turn the question into SQL."""


def gold_structured_path() -> Path:
    """`gold/structured` under the M2 data lake root (relative roots resolve from the repo root)."""
    root = Path(get_settings().data_lake_path)
    return (root if root.is_absolute() else REPO_ROOT / root) / "gold" / "structured"


def _safe_select(sql: str) -> str:
    """Return the statement unchanged if it is a single SELECT; otherwise raise UnsafeSQLError."""
    stmt = sql.strip().removesuffix(";").strip()
    if not stmt:
        raise UnsafeSQLError("empty SQL")
    if ";" in stmt:
        raise UnsafeSQLError("multiple statements are not allowed")
    if not re.match(r"select\b", stmt, re.IGNORECASE):
        raise UnsafeSQLError("only SELECT statements are allowed")
    if match := _FORBIDDEN.search(stmt):
        raise UnsafeSQLError(f"forbidden keyword in SQL: {match.group(0).upper()}")
    # A FROM-less SELECT (e.g. `SELECT price`) is syntactically fine but fails at bind time.
    if not re.search(r"\bfrom\b", stmt, re.IGNORECASE):
        raise UnsafeSQLError("SELECT must read FROM the table")
    return stmt


def _connect(scope: Filters | None = None) -> duckdb.DuckDBPyConnection:
    path = gold_structured_path()
    if not path.exists():
        raise FileNotFoundError(f"Gold structured not found at {path}; run the M2 pipeline first.")
    table = DeltaTable(str(path)).to_pyarrow_table()
    conn = duckdb.connect(":memory:")
    conn.register("_gold", table)
    # Scope is applied to the data itself, so generated SQL can never see rows outside it.
    where, params = "", []
    if category := (scope or {}).get("category"):
        values = [category] if isinstance(category, str) else list(category)
        where = f" WHERE category IN ({', '.join('?' for _ in values)})"
        params = values
    conn.execute(f"CREATE TABLE {TABLE} AS SELECT * FROM _gold{where}", params)
    conn.unregister("_gold")
    conn.execute("SET enable_external_access = false")
    return conn


def run_sql(sql: str, scope: Filters | None = None) -> dict:
    """Validate then execute; DuckDB computes every number, so results are exact."""
    stmt = _safe_select(sql)
    conn = _connect(scope)
    try:
        cursor = conn.execute(stmt)
        columns = [d[0] for d in cursor.description]
        rows = [list(r) for r in cursor.fetchmany(MAX_ROWS)]
    finally:
        conn.close()
    return {"sql": stmt, "rows": rows, "columns": columns}


def _columns() -> list[str]:
    return [f.name for f in DeltaTable(str(gold_structured_path())).schema().fields]


async def generate_sql(query: str, ledger: CostLedger) -> str:
    llm = get_llm()
    if not llm.available:
        raise SQLGenerationUnavailable(
            "SQL generation needs an LLM; set FREE_LLM_BASE_URL/FREE_LLM_MODEL or use azure mode."
        )
    system = SYSTEM_PROMPT.format(table=TABLE, columns=", ".join(_columns()))
    raw = await llm.complete(system, query, ledger=ledger)
    return re.sub(r"^```(?:sql)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)


async def sql_agent(query: str, scope: Filters | None, ledger: CostLedger) -> dict:
    """Text-to-SQL over Gold `structured`; returns {sql, rows, columns}.

    A bad statement (guard rejection or DuckDB error) is regenerated once; a second failure raises
    SQLComputeError. SQLGenerationUnavailable is a refusal, not a failure, and is never retried.
    """
    for attempt in (1, 2):
        sql = await generate_sql(query, ledger)
        try:
            return run_sql(sql, scope)
        except (UnsafeSQLError, duckdb.Error) as exc:
            log.warning("sql attempt %d failed: %s: %s", attempt, type(exc).__name__, exc)
    raise SQLComputeError("Could not compute a valid SQL answer for this question.")
