"""Test-session isolation for the Postgres-backed suites.

Several suites (`test_vector_store`, `test_pipeline`, `test_index_reviews`,
`test_index_docs`, `test_hybrid`, the memory/threads suites, …) DROP and recreate
`chunks` / `messages` / `threads` / `user_memory` for a clean slate. Their fixtures
read the DB URL via `Settings()` (i.e. from `.env`), which in local dev points at the
real `rag` database holding the embedded corpus — so running them there destroys it
(it did, twice, 2026-11-01).

This redirects the whole test session to a dedicated `<db>_test` database, creating
it if needed. It reads the configured URL **the same way the app does** — through
`Settings()`, not `os.environ`, because the real value lives in the `.env` file, not
the shell environment. It **fails closed**: if a database is configured but a `_test`
target cannot be positively confirmed, it aborts the session rather than letting a
test touch the real DB. When no database is configured at all, DB-backed fixtures
already skip themselves, so this is a no-op.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import psycopg

from app.config import Settings, get_settings


def _configured_url() -> str | None:
    """The DB URL exactly as the app resolves it (TEST_DATABASE_URL wins, else .env)."""
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        return override
    url = Settings().database_url
    return url.get_secret_value() if url is not None else None


def _with_dbname(url: str, name: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{name}"))


def _ensure_database(url: str) -> None:
    """Create the target database if absent, via the `postgres` maintenance DB."""
    name = urlsplit(url).path.lstrip("/")
    with psycopg.connect(_with_dbname(url, "postgres"), autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [name]).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')


def pytest_configure(config: object) -> None:  # noqa: ARG001 (pytest hook signature)
    base = _configured_url()
    if base is None:
        return  # no DB configured -> DB-backed fixtures skip themselves; nothing to isolate

    name = urlsplit(base).path.lstrip("/")
    test_name = name if name.endswith("_test") else f"{name}_test"
    test_url = _with_dbname(base, test_name)

    # Fail CLOSED: never proceed unless the target is unambiguously a *_test database.
    if not test_name.endswith("_test"):
        raise RuntimeError(f"refusing to run DB tests: {test_name!r} is not a *_test database")

    _ensure_database(test_url)  # a failure here aborts the session rather than hitting the real DB

    # Point every Settings()/get_settings() lookup at the isolated DB. An env var set here
    # takes precedence over the .env file, so all fixtures resolve to the *_test database.
    os.environ["DATABASE_URL"] = test_url
    get_settings.cache_clear()  # drop any value cached before the override
