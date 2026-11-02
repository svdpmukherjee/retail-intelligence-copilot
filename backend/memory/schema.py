from datetime import datetime
from typing import Literal

from pydantic import BaseModel

THREADS_TABLE = "threads"
MESSAGES_TABLE = "messages"
MEMORY_TABLE = "user_memory"

THREAD_COLUMNS = ("id", "user_id", "role", "created_at")
MESSAGE_COLUMNS = ("id", "thread_id", "turn", "role_kind", "content", "payload", "created_at")
MEMORY_COLUMNS = ("id", "user_id", "kind", "content", "scope", "created_at")

RoleKind = Literal["user", "assistant"]
MemoryKind = Literal["preference", "finding"]


class ThreadRow(BaseModel):
    id: str
    user_id: str
    role: str
    created_at: datetime


class ThreadListRow(BaseModel):
    id: str
    label: str
    created_at: datetime
    turn_count: int


class MessageRow(BaseModel):
    id: int
    thread_id: str
    turn: int
    role_kind: RoleKind
    content: str
    # Full render snapshot for an assistant turn (answer, citations, sql block, render audit),
    # so reopening a chat replays its charts and evidence, not just stripped text. None for user
    # turns and for turns written before this column existed.
    payload: dict | None = None
    created_at: datetime


class MemoryRow(BaseModel):
    id: int
    user_id: str
    kind: MemoryKind
    content: str
    scope: dict
    created_at: datetime


def memory_ddl() -> list[str]:
    return [
        f"""CREATE TABLE IF NOT EXISTS {THREADS_TABLE} (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
        f"CREATE INDEX IF NOT EXISTS threads_user_idx ON {THREADS_TABLE} (user_id)",
        f"""CREATE TABLE IF NOT EXISTS {MESSAGES_TABLE} (
            id BIGSERIAL PRIMARY KEY,
            thread_id TEXT NOT NULL REFERENCES {THREADS_TABLE} (id) ON DELETE CASCADE,
            turn INTEGER NOT NULL,
            role_kind TEXT NOT NULL CHECK (role_kind IN ('user', 'assistant')),
            content TEXT NOT NULL,
            payload JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
        # Migrate message tables created before replay snapshots existed (idempotent).
        f"ALTER TABLE {MESSAGES_TABLE} ADD COLUMN IF NOT EXISTS payload JSONB",
        "CREATE INDEX IF NOT EXISTS messages_thread_turn_idx "
        f"ON {MESSAGES_TABLE} (thread_id, turn)",
        f"""CREATE TABLE IF NOT EXISTS {MEMORY_TABLE} (
            id BIGSERIAL PRIMARY KEY,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('preference', 'finding')),
            content TEXT NOT NULL,
            scope JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
        f"CREATE INDEX IF NOT EXISTS user_memory_user_idx ON {MEMORY_TABLE} (user_id)",
    ]
