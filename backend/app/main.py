"""FastAPI application entry point with safe error handling, CORS, and lifespan."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import init_db
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.routes.sessions import router as sessions_router
from app.services.cache import init_litellm_cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize SQLite schema and LiteLLM cache at startup."""
    settings = get_settings()
    init_db(settings.sqlite_db_path)
    init_litellm_cache(settings)

    key_count = len(settings.key_pool)
    if key_count == 0:
        logger.warning("LLM_API_KEYS is empty. /health will return 503 until configured.")
    elif key_count == 1:
        logger.warning("Only 1 API key configured. At least 2 keys are recommended for failover.")
    else:
        logger.info("Configured %d logical LLM API keys.", key_count)

    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Lyftr AI Gateway",
        description="Resilient LLM Chatbot with Key Failover and LiteLLM Response Caching",
        version="1.0.0",
        lifespan=lifespan,
    )

    allowed_origins = settings.allowed_origins_list
    use_credentials = "*" not in allowed_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=use_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
            msg = first.get("msg", "validation error")
            detail = f"{loc}: {msg}" if loc else str(msg)
        else:
            detail = "invalid request payload"
        return JSONResponse(
            status_code=422,
            content={"detail": detail},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request, _exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled server exception.")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)

    return app


app = create_app()
