"""Session history endpoint."""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.models.message import get_session_messages
from app.schemas.chat import SessionMessage, SessionMessagesResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])


@router.get(
    "/sessions/{session_id}/messages",
    response_model=SessionMessagesResponse,
    response_model_exclude_none=True,
)
def get_session_history(
    session_id: str,
    settings: Settings = Depends(get_settings),
) -> SessionMessagesResponse:
    """Return oldest-first SQLite history for a session, excluding system prompt."""
    db_path = settings.sqlite_db_path

    try:
        stored_messages = get_session_messages(db_path, session_id)
    except (sqlite3.Error, OSError) as exc:
        logger.exception("Database read failed for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc

    if not stored_messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found",
        )

    messages = [
        SessionMessage(
            role=msg.role,  # type: ignore[arg-type]
            content=msg.content,
            metadata=msg.metadata if msg.role == "assistant" else None,
        )
        for msg in stored_messages
    ]
    return SessionMessagesResponse(session_id=session_id, messages=messages)
