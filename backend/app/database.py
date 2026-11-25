"""SQLite database connection management and schema initialization."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    system_prompt TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id_id
    ON messages (session_id, id);
"""


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent_dir(db_path: str) -> None:
    if db_path == ":memory:" or db_path.startswith("file:"):
        return
    parent = os.path.dirname(os.path.abspath(db_path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def create_connection(db_path: str) -> sqlite3.Connection:
    """Open a configured SQLite connection."""
    _ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000;")
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def db_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a SQLite connection and closing it cleanly."""
    conn = create_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    """Create database tables and indexes if they do not already exist."""
    with db_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    logger.info("SQLite database initialized.")


def check_db_health(db_path: str) -> bool:
    """Verify SQLite is reachable and schema exists."""
    try:
        with db_connection(db_path) as conn:
            conn.execute("SELECT 1 FROM messages LIMIT 1;")
        return True
    except sqlite3.Error:
        logger.exception("SQLite health check failed.")
        return False
    except OSError:
        logger.exception("SQLite filesystem health check failed.")
        return False
