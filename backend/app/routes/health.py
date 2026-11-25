"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.database import check_db_health
from app.schemas.chat import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Return 200 OK only when app, SQLite database, and API key pool are ready."""
    try:
        db_path = settings.sqlite_db_path
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database configuration invalid",
        ) from exc

    if not check_db_health(db_path):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        )

    keys_configured = len(settings.key_pool)
    if keys_configured == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="no api keys configured",
        )

    return HealthResponse(
        status="ok",
        keys_configured=keys_configured,
        cache_enabled=settings.cache_enabled,
    )
