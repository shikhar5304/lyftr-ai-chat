"""SQLite repository functions for sessions and messages."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from app.database import db_connection, utc_now_iso


@dataclass(frozen=True)
class StoredMessage:
    """Domain representation of a persisted chat message."""

    id: int
    session_id: str
    role: str
    content: str
    metadata: dict[str, Any] | None
    created_at: str


def _row_to_message(row: sqlite3.Row) -> StoredMessage:
    raw_meta = row["metadata"]
    parsed_meta: dict[str, Any] | None = None
    if raw_meta:
        try:
            loaded = json.loads(raw_meta)
            if isinstance(loaded, dict):
                parsed_meta = loaded
        except json.JSONDecodeError:
            parsed_meta = None

    return StoredMessage(
        id=int(row["id"]),
        session_id=str(row["session_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        metadata=parsed_meta,
        created_at=str(row["created_at"]),
    )


def get_session_messages(db_path: str, session_id: str) -> list[StoredMessage]:
    """Return all messages for a session ordered oldest-first."""
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, role, content, metadata, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    return [_row_to_message(row) for row in rows]


def get_session_system_prompt(db_path: str, session_id: str) -> str | None:
    """Return the persisted custom system prompt for a session, if any."""
    with db_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT system_prompt
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    value = row["system_prompt"]
    return str(value) if value else None


def save_conversation_turn(
    db_path: str,
    session_id: str,
    user_content: str,
    assistant_content: str,
    assistant_metadata: dict[str, Any],
    system_prompt: str | None = None,
) -> None:
    """Atomically persist both the user message and successful assistant response."""
    now = utc_now_iso()
    metadata_json = json.dumps(assistant_metadata, separators=(",", ":"))

    with db_connection(db_path) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, system_prompt, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    system_prompt = COALESCE(excluded.system_prompt, sessions.system_prompt),
                    updated_at = excluded.updated_at
                """,
                (session_id, system_prompt, now, now),
            )
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, 'user', ?, NULL, ?)
                """,
                (session_id, user_content, now),
            )
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, 'assistant', ?, ?, ?)
                """,
                (session_id, assistant_content, metadata_json, now),
            )
