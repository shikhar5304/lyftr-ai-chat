"""Pytest configuration and shared fixtures for backend tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture()
def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Factory fixture creating a TestClient with isolated SQLite DB and env config."""
    clients: list[TestClient] = []

    def _create(
        *,
        api_keys: str = "test-secret-key-one,test-secret-key-two",
        enable_failure_simulation: str = "true",
        cache_enabled: str = "true",
        db_url: str | None = None,
    ) -> TestClient:
        resolved_db = db_url or f"sqlite:///{tmp_path / 'test_app.db'}"
        monkeypatch.setenv("LLM_API_KEYS", api_keys)
        monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
        monkeypatch.setenv("DATABASE_URL", resolved_db)
        monkeypatch.setenv("ENABLE_FAILURE_SIMULATION", enable_failure_simulation)
        monkeypatch.setenv("CACHE_ENABLED", cache_enabled)
        monkeypatch.setenv("LITELLM_CACHE_TYPE", "local")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")

        get_settings.cache_clear()
        app = create_app()
        tc = TestClient(app)
        tc.__enter__()
        clients.append(tc)
        return tc

    yield _create

    for tc in reversed(clients):
        tc.__exit__(None, None, None)
    get_settings.cache_clear()


@pytest.fixture()
def client(make_client) -> Iterator[TestClient]:
    """Default TestClient with 2 configured keys, local cache, and simulation enabled."""
    yield make_client()
