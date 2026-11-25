"""Key failover policy and X-Simulate-Failure evaluation hook."""

from __future__ import annotations

import asyncio
import os
from typing import Final

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm

SUPPORTED_SIMULATED_STATUSES: Final[frozenset[int]] = frozenset({429, 500, 502, 503})

RETRYABLE_LITELLM_EXCEPTIONS: tuple[type[BaseException], ...] = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.InternalServerError,
    litellm.exceptions.BadGatewayError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.Timeout,
    litellm.exceptions.APIConnectionError,
    asyncio.TimeoutError,
    TimeoutError,
)


class AllProvidersUnavailableError(Exception):
    """Raised when every configured API key fails during a chat request."""


class EmptyProviderResponseError(Exception):
    """Raised when the provider returns an empty or malformed response."""


def parse_failure_simulation_header(
    header_value: str | None,
    enabled: bool,
) -> dict[str, int]:
    """
    Parse X-Simulate-Failure header into a map of key_id (or '*') -> HTTP status code.

    Example: 'key_1=429,key_2=500' or '*=429'.
    Returns an empty dict when failure simulation is disabled or header is absent.
    """
    if not enabled or not header_value:
        return {}

    rules: dict[str, int] = {}
    for raw_part in header_value.split(","):
        part = raw_part.strip()
        if "=" not in part:
            continue
        key_part, status_part = part.split("=", 1)
        key_name = key_part.strip()
        status_str = status_part.strip()
        if not key_name or not status_str.isdigit():
            continue
        status_code = int(status_str)
        if status_code in SUPPORTED_SIMULATED_STATUSES:
            rules[key_name] = status_code
    return rules


def get_simulated_status(rules: dict[str, int], key_id: str) -> int | None:
    """Return the simulated failure HTTP status for key_id, or None if not simulated."""
    if key_id in rules:
        return rules[key_id]
    if "*" in rules:
        return rules["*"]
    return None


def build_simulated_exception(status_code: int, model: str, key_id: str) -> Exception:
    """Construct an authentic LiteLLM exception matching the simulated HTTP status."""
    provider = model.split("/", 1)[0] if "/" in model else "openai"
    message = f"Simulated provider failure ({status_code}) for {key_id}"

    if status_code == 429:
        return litellm.exceptions.RateLimitError(
            message=message,
            llm_provider=provider,
            model=model,
        )
    if status_code == 500:
        return litellm.exceptions.InternalServerError(
            message=message,
            llm_provider=provider,
            model=model,
        )
    if status_code == 502:
        return litellm.exceptions.BadGatewayError(
            message=message,
            llm_provider=provider,
            model=model,
        )
    return litellm.exceptions.ServiceUnavailableError(
        message=message,
        llm_provider=provider,
        model=model,
    )


def is_retryable_error(exc: BaseException) -> bool:
    """Return True for 429, quota exhaustion, 5xx, timeout, and transient provider errors."""
    if isinstance(exc, RETRYABLE_LITELLM_EXCEPTIONS):
        return True
    if isinstance(exc, EmptyProviderResponseError):
        return True

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int) and (status_code == 429 or status_code >= 500):
        return True

    text = str(exc).lower()
    retry_markers = (
        "429",
        "rate limit",
        "ratelimit",
        "quota",
        "resource exhausted",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "temporarily unavailable",
        "overloaded",
    )
    return any(marker in text for marker in retry_markers)
