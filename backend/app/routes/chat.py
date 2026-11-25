"""Chat completion endpoint."""

from __future__ import annotations

import logging
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import Settings, get_settings
from app.models.message import (
    get_session_messages,
    get_session_system_prompt,
    save_conversation_turn,
)
from app.schemas.chat import ChatMetadata, ChatRequest, ChatResponse
from app.services.failover import AllProvidersUnavailableError
from app.services.llm_service import generate_chat_completion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    x_simulate_failure: str | None = Header(default=None, alias="X-Simulate-Failure"),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """Handle multi-turn chat with SQLite context reconstruction, failover, and caching."""
    db_path = settings.sqlite_db_path

    try:
        history = get_session_messages(db_path, payload.session_id)
        stored_prompt = get_session_system_prompt(db_path, payload.session_id)
    except (sqlite3.Error, OSError) as exc:
        logger.exception("Database read failed for session %s", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc

    effective_system_prompt = (
        payload.system_prompt
        or stored_prompt
        or (settings.default_system_prompt.strip() or None)
    )

    try:
        result = await generate_chat_completion(
            settings=settings,
            history=history,
            new_user_message=payload.message,
            system_prompt=effective_system_prompt,
            simulate_failure_header=x_simulate_failure,
        )
    except AllProvidersUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="all providers unavailable",
        ) from exc

    metadata = ChatMetadata(
        resolution_source=result.resolution_source,  # type: ignore[arg-type]
        model=result.model,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        key_id=result.key_id,
        fallback_attempts=result.fallback_attempts,
    )

    try:
        save_conversation_turn(
            db_path=db_path,
            session_id=payload.session_id,
            user_content=payload.message,
            assistant_content=result.reply,
            assistant_metadata=metadata.model_dump(),
            system_prompt=payload.system_prompt,
        )
    except (sqlite3.Error, OSError) as exc:
        logger.exception("Database write failed for session %s", payload.session_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc

    return ChatResponse(
        session_id=payload.session_id,
        reply=result.reply,
        metadata=metadata,
    )
