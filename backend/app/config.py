"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class KeyEntry:
    """Represents a single logical LLM API key without exposing the secret in logs/responses."""

    key_id: str
    api_key: str

    def __repr__(self) -> str:
        return f"KeyEntry(key_id={self.key_id!r}, api_key='***')"


class Settings(BaseSettings):
    """Runtime settings parsed from environment variables and optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    llm_api_keys: str = Field(default="", alias="LLM_API_KEYS")
    llm_model: str = Field(default="gemini/gemini-2.0-flash", alias="LLM_MODEL")
    default_system_prompt: str = Field(
        default="You are a helpful, concise, and accurate AI assistant.",
        alias="DEFAULT_SYSTEM_PROMPT",
    )
    llm_timeout_seconds: float = Field(default=30.0, alias="LLM_TIMEOUT_SECONDS")

    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    litellm_cache_type: Literal["local", "disk"] = Field(
        default="local", alias="LITELLM_CACHE_TYPE"
    )
    litellm_disk_cache_dir: str = Field(
        default="/tmp/litellm_cache", alias="LITELLM_DISK_CACHE_DIR"
    )

    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")
    allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173",
        alias="ALLOWED_ORIGINS",
    )
    enable_failure_simulation: bool = Field(
        default=False, alias="ENABLE_FAILURE_SIMULATION"
    )

    @property
    def key_pool(self) -> list[KeyEntry]:
        """Parse comma-separated API keys into ordered logical key_1, key_2, ... entries."""
        raw_keys = [part.strip() for part in self.llm_api_keys.split(",") if part.strip()]
        return [
            KeyEntry(key_id=f"key_{idx}", api_key=secret)
            for idx, secret in enumerate(raw_keys, start=1)
        ]

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated CORS allowed origins."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def sqlite_db_path(self) -> str:
        """Extract filesystem path (or :memory:) from SQLite DATABASE_URL."""
        url = self.database_url.strip()
        if not url.startswith("sqlite:///"):
            raise ValueError("Only SQLite DATABASE_URL (sqlite:///...) is supported.")

        raw_path = url[len("sqlite:///") :]
        if raw_path == ":memory:":
            return ":memory:"

        # sqlite:////data/app.db leaves raw_path="/data/app.db" (POSIX absolute path).
        # sqlite:///./data/app.db leaves raw_path="./data/app.db" (relative path).
        # On Windows, sqlite:///C:/... leaves raw_path="C:/...".
        return str(Path(raw_path)) if not raw_path.startswith("/") else raw_path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
