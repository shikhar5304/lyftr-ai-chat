"""LiteLLM built-in response cache configuration and detection helpers."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import Settings

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from litellm.caching.caching import Cache

logger = logging.getLogger(__name__)


def init_litellm_cache(settings: Settings) -> bool:
    """Configure LiteLLM's built-in response cache based on application settings."""
    if not settings.cache_enabled:
        litellm.cache = None
        logger.info("LiteLLM response cache is disabled.")
        return False

    cache_type = settings.litellm_cache_type
    if cache_type == "disk":
        os.makedirs(settings.litellm_disk_cache_dir, exist_ok=True)
        litellm.cache = Cache(
            type="disk",
            disk_cache_dir=settings.litellm_disk_cache_dir,
            max_messages=None,
        )
        logger.info("LiteLLM disk cache enabled at %s.", settings.litellm_disk_cache_dir)
    else:
        litellm.cache = Cache(
            type="local",
            max_messages=None,
        )
        logger.info("LiteLLM local in-memory cache enabled.")

    return True


def is_response_from_cache(response: Any) -> bool:
    """Determine reliably from LiteLLM response metadata whether it came from cache."""
    hidden_params = getattr(response, "_hidden_params", None)
    if isinstance(hidden_params, dict):
        return bool(hidden_params.get("cache_hit", False))
    return False
