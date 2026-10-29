import uuid

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import get_settings
from memory.schema import (
    MEMORY_COLUMNS,
    MEMORY_TABLE,
    MESSAGE_COLUMNS,
    MESSAGES_TABLE,
    THREAD_COLUMNS,
    THREADS_TABLE,
    MemoryKind,
    MemoryRow,
    MessageRow,
    RoleKind,
    ThreadListRow,
    ThreadRow,
    memory_ddl,
)
from retrieval.vector_store import Filters

_THREAD_COLS = ", ".join(THREAD_COLUMNS)
_MESSAGE_COLS = ", ".join(f"m.{c}" for c in MESSAGE_COLUMNS)
_MEMORY_COLS = ", ".join(MEMORY_COLUMNS)
_LABEL_CHARS = 48


class MemoryStore:
    """Threads, messages and durable user memory in Postgres. Connects per call, like
    PgVectorStore. Every query is parameterised and scoped by user_id / thread_id."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._url, row_factory=dict_row)

    def ensure_schema(self) -> None:
        with self._connect() as conn:
            for statement in memory_ddl():
                conn.execute(statement)

    def create_thread(self, user_id: str, role: str) -> ThreadRow:
        sql = (
            f"INSERT INTO {THREADS_TABLE} (id, user_id, role) VALUES (%s, %s, %s) "
            f"RETURNING {_THREAD_COLS}"
        )
        with self._connect() as conn:
            row = conn.execute(sql, [uuid.uuid4().hex, user_id, role]).fetchone()
        return ThreadRow(**row)

    def get_thread(self, thread_id: str, user_id: str) -> ThreadRow | None:
        """The thread only if `user_id` owns it; unknown or foreign threads give None."""
        sql = f"SELECT {_THREAD_COLS} FROM {THREADS_TABLE} WHERE id = %s AND user_id = %s"
        with self._connect() as conn:
            row = conn.execute(sql, [thread_id, user_id]).fetchone()
        return ThreadRow(**row) if row else None

    def list_threads(self, user_id: str, role: str) -> list[ThreadListRow]:
        """The user's threads under one role, newest first. The label is the first user
        message (already PII-redacted at write time), cut to _LABEL_CHARS. Threads with no
        persisted turn yet are skipped."""
        sql = (
            "SELECT t.id, t.created_at, COALESCE((SELECT LEFT(f.content, %s) "
            f"FROM {MESSAGES_TABLE} f WHERE f.thread_id = t.id AND f.role_kind = 'user' "
            "ORDER BY f.turn LIMIT 1), '') AS label, COUNT(m.id) AS turn_count "
            f"FROM {THREADS_TABLE} t LEFT JOIN {MESSAGES_TABLE} m ON m.thread_id = t.id "
            "WHERE t.user_id = %s AND t.role = %s GROUP BY t.id "
            "HAVING COUNT(m.id) > 0 ORDER BY t.created_at DESC"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, [_LABEL_CHARS, user_id, role]).fetchall()
        return [ThreadListRow(**r) for r in rows]

    def append_message(
        self, thread_id: str, role_kind: RoleKind, content: str, *, user_id: str
    ) -> MessageRow:
        """Append only if `user_id` owns the thread; a non-owner (or unknown thread) raises."""
        # turn is assigned in the INSERT; the (thread_id, turn) index keeps reads ordered.
        sql = (
            f"INSERT INTO {MESSAGES_TABLE} (thread_id, turn, role_kind, content) "
            f"SELECT %s, COALESCE(MAX(turn), 0) + 1, %s, %s FROM {MESSAGES_TABLE} "
            f"WHERE thread_id = %s HAVING EXISTS "
            f"(SELECT 1 FROM {THREADS_TABLE} WHERE id = %s AND user_id = %s) "
            "RETURNING " + ", ".join(MESSAGE_COLUMNS)
        )
        with self._connect() as conn:
            row = conn.execute(
                sql, [thread_id, role_kind, content, thread_id, thread_id, user_id]
            ).fetchone()
        if row is None:
            raise PermissionError(f"thread {thread_id!r} is not owned by this user")
        return MessageRow(**row)

    def recent_messages(
        self, thread_id: str, limit: int, *, user_id: str | None = None
    ) -> list[MessageRow]:
        """Newest `limit` messages, oldest first. With user_id, only if the user owns the thread."""
        owner = ""
        params: list[object] = [thread_id]
        if user_id is not None:
            owner = f"AND m.thread_id IN (SELECT id FROM {THREADS_TABLE} WHERE user_id = %s) "
            params.append(user_id)
        sql = (
            f"SELECT {_MESSAGE_COLS} FROM {MESSAGES_TABLE} m WHERE m.thread_id = %s {owner}"
            "ORDER BY m.turn DESC LIMIT %s"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, [*params, limit]).fetchall()
        return [MessageRow(**r) for r in reversed(rows)]

    def add_memory(self, user_id: str, kind: MemoryKind, content: str, scope: dict) -> MemoryRow:
        sql = (
            f"INSERT INTO {MEMORY_TABLE} (user_id, kind, content, scope) "
            f"VALUES (%s, %s, %s, %s) RETURNING {_MEMORY_COLS}"
        )
        with self._connect() as conn:
            row = conn.execute(sql, [user_id, kind, content, Jsonb(scope)]).fetchone()
        return MemoryRow(**row)

    def list_memory(
        self,
        user_id: str,
        *,
        kind: MemoryKind | None = None,
        limit: int,
        scope: Filters | None = None,
    ) -> list[MemoryRow]:
        """With `scope`, keep only rows whose stamped scope names every scoped key and whose
        values all lie inside the allowed set; unscoped (`{}`) rows are hidden from scoped roles."""
        clauses = ["user_id = %s"]
        params: list[object] = [user_id]
        if kind:
            clauses.append("kind = %s")
            params.append(kind)
        for key, allowed in (scope or {}).items():
            allowed_list = [allowed] if isinstance(allowed, str) else list(allowed)
            clauses.append(
                "(CASE WHEN jsonb_typeof(scope -> %s) = 'array' THEN scope -> %s "
                "ELSE jsonb_build_array(scope -> %s) END) <@ %s"
            )
            params += [key, key, key, Jsonb(allowed_list)]
            clauses.append("scope ? %s")
            params.append(key)
        sql = (
            f"SELECT {_MEMORY_COLS} FROM {MEMORY_TABLE} WHERE {' AND '.join(clauses)} "
            "ORDER BY id DESC LIMIT %s"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, [*params, limit]).fetchall()
        return [MemoryRow(**r) for r in rows]

    def trim_memory(self, user_id: str, keep: int) -> None:
        """Keep only the newest `keep` durable rows for the user; older ones are deleted."""
        sql = (
            f"DELETE FROM {MEMORY_TABLE} WHERE user_id = %s AND id NOT IN "
            f"(SELECT id FROM {MEMORY_TABLE} WHERE user_id = %s ORDER BY id DESC LIMIT %s)"
        )
        with self._connect() as conn:
            conn.execute(sql, [user_id, user_id, keep])


def get_memory_store() -> MemoryStore:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not set; it is required for conversation memory.")
    return MemoryStore(settings.database_url.get_secret_value())
