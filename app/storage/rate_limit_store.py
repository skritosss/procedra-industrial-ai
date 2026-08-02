"""Storage for rate-limit buckets, kept out of the business database.

SQLite allows one writer. Every throttled request writes here, and those writes
had been landing in the same database that holds users, sessions, instructions
and the audit trail — so limiter bookkeeping queued behind, and ahead of, real
work. The metrics store was split out for exactly this reason; the limiter was
left behind.

The data is disposable by construction: rows are time-windowed counters that are
deleted as they age. Nothing is migrated when this file is created, and losing it
costs at most one window of accounting.
"""

from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3

RATE_LIMIT_SCHEMA_VERSION = 1


def connect_rate_limit_store(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


_INITIALIZED_PATHS: set[str] = set()


def reset_rate_limit_store_cache() -> None:
    _INITIALIZED_PATHS.clear()


def initialize_rate_limit_store(database_path: Path, *, force: bool = False) -> None:
    """Create the schema, at most once per file per process.

    The schema is created at startup, and once per file for callers that pass
    their own path. Doing it on every request would reintroduce the write per
    request that this separate database exists to remove.
    """
    key = str(database_path.resolve())
    if not force and key in _INITIALIZED_PATHS:
        return
    with closing(connect_rate_limit_store(database_path)) as connection:
        _apply_schema(connection)
    os.chmod(database_path, 0o600)
    _INITIALIZED_PATHS.add(key)


def rate_limit_store_is_ready(database_path: Path) -> bool:
    try:
        initialize_rate_limit_store(database_path)
    except (OSError, sqlite3.Error, ValueError):
        return False
    return True


def _apply_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limit_schema (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            version INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS rate_limit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bucket_hash TEXT NOT NULL,
            occurred_at REAL NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_rate_limit_bucket_time ON rate_limit_events (bucket_hash, occurred_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_rate_limit_event_time ON rate_limit_events (occurred_at)"
    )
    connection.execute(
        "INSERT OR REPLACE INTO rate_limit_schema (singleton, version) VALUES (1, ?)",
        (RATE_LIMIT_SCHEMA_VERSION,),
    )
    connection.commit()
