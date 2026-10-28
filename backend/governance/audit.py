import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings
from governance.pii import redact

AUDIT_TABLE = "audit_log"
_schema_ready = False


def audit_ddl() -> list[str]:
    return [
        f"""CREATE TABLE IF NOT EXISTS {AUDIT_TABLE} (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            query TEXT NOT NULL,
            role TEXT NOT NULL,
            intent TEXT,
            tool_path JSONB NOT NULL DEFAULT '[]'::jsonb,
            sources JSONB NOT NULL DEFAULT '[]'::jsonb,
            tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
            grounding JSONB,
            memory JSONB
        )""",
        f"CREATE INDEX IF NOT EXISTS audit_log_created_idx ON {AUDIT_TABLE} (created_at)",
    ]


class AuditStore:
    """Durable audit trail in Postgres. Connects per call, like MemoryStore. Stores the audit
    dict as built upstream: redacted content and ids, never secrets."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._url, row_factory=dict_row)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            for statement in audit_ddl():
                conn.execute(statement)

    def record(self, audit: dict) -> None:
        sql = (
            f"INSERT INTO {AUDIT_TABLE} (query, role, intent, tool_path, sources, tokens, "
            "cost_usd, latency_ms, grounding, memory) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        grounding, memory = audit.get("grounding"), audit.get("memory")
        params = [
            redact(audit["query"]),  # user text may carry PII; the audit log keeps it redacted
            audit["role"],
            audit.get("intent"),
            Jsonb(audit.get("tool_path", [])),
            Jsonb(audit.get("sources", [])),
            audit.get("tokens", 0),
            audit.get("cost_usd", 0),
            audit.get("latency_ms", 0),
            None if grounding is None else Jsonb(grounding),
            None if memory is None else Jsonb(memory),
        ]
        with self._connect() as conn:
            conn.execute(sql, params)


def get_audit_store() -> AuditStore:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not set; it is required for the audit log.")
    return AuditStore(settings.database_url.get_secret_value())


def ensure_audit_schema() -> None:
    """Create the audit table once per process (the DDL is also IF NOT EXISTS)."""
    global _schema_ready
    if not _schema_ready:
        get_audit_store().ensure_schema()
        _schema_ready = True


def record_audit(audit: dict) -> None:
    ensure_audit_schema()
    get_audit_store().record(audit)
