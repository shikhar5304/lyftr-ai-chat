"""LiteLLM orchestration service with key failover, caching, token tracking, and latency."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
from litellm.types.utils import ModelResponse

from app.config import Settings
from app.models.message import StoredMessage
from app.services.failover import (
    AllProvidersUnavailableError,
    EmptyProviderResponseError,
    build_simulated_exception,
    get_simulated_status,
    is_retryable_error,
    parse_failure_simulation_header,
)

litellm.telemetry = False
litellm.suppress_debug_info = True

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResult:
    reply: str
    resolution_source: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: str | None
    fallback_attempts: int


def build_llm_messages(history: list[StoredMessage], new_user_message: str, system_prompt: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": new_user_message})
    return messages


def _extract_reply_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise EmptyProviderResponseError("Provider returned no choices.")
    first = choices[0]
    message = getattr(first, "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if not isinstance(content, str) or not content.strip():
        raise EmptyProviderResponseError("Provider returned empty reply content.")
    return content


def _extract_token_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
    else:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    return int(prompt_tokens), int(completion_tokens)


def _restore_cached_response(cached: Any) -> Any:
    if isinstance(cached, ModelResponse):
        return cached
    if isinstance(cached, dict):
        return ModelResponse(**cached)
    return cached


async def generate_chat_completion(
    settings: Settings,
    history: list[StoredMessage],
    new_user_message: str,
    system_prompt: str | None,
    simulate_failure_header: str | None = None,
) -> LLMResult:
    key_pool = settings.key_pool
    if not key_pool:
        logger.error("No LLM API keys are configured.")
        raise AllProvidersUnavailableError("No LLM API keys configured.")

    messages = build_llm_messages(history, new_user_message, system_prompt)
    simulation_rules = parse_failure_simulation_header(simulate_failure_header, enabled=settings.enable_failure_simulation)
    bypass_cache = bool(simulation_rules)
    start_ns = time.perf_counter_ns()

    # Use LiteLLM's built-in Cache object directly. This makes cache lookup independent
    # of provider/key availability and guarantees the required model + full-message key.
    if settings.cache_enabled and not bypass_cache and litellm.cache is not None:
        try:
            cached = await litellm.cache.async_get_cache(model=settings.llm_model, messages=messages, caching=True)
            if cached is not None:
                response = _restore_cached_response(cached)
                reply_text = _extract_reply_text(response)
                input_tokens, output_tokens = _extract_token_usage(response)
                elapsed_ms = max(1, int((time.perf_counter_ns() - start_ns) // 1_000_000))
                response_model = getattr(response, "model", None) or settings.llm_model
                return LLMResult(reply_text, "LLM_CACHE", str(response_model), elapsed_ms, input_tokens, output_tokens, None, 0)
        except Exception as exc:
            logger.warning("LiteLLM cache read failed; continuing with live inference: %s: %s", type(exc).__name__, exc)

    failed_attempts = 0
    for entry in key_pool:
        simulated_status = get_simulated_status(simulation_rules, entry.key_id)
        try:
            if simulated_status is not None:
                raise build_simulated_exception(simulated_status, model=settings.llm_model, key_id=entry.key_id)

            response = await litellm.acompletion(
                model=settings.llm_model,
                messages=messages,
                api_key=entry.api_key,
                timeout=settings.llm_timeout_seconds,
                caching=False,  # cache is managed explicitly above/below via LiteLLM Cache
                cache={"no-cache": True, "no-store": True},
            )
            reply_text = _extract_reply_text(response)
            input_tokens, output_tokens = _extract_token_usage(response)
            elapsed_ms = max(1, int((time.perf_counter_ns() - start_ns) // 1_000_000))
            response_model = getattr(response, "model", None) or settings.llm_model

            if settings.cache_enabled and not bypass_cache and litellm.cache is not None:
                try:
                    await litellm.cache.async_add_cache(response, model=settings.llm_model, messages=messages, caching=True)
                except Exception as exc:
                    logger.warning("LiteLLM cache write failed: %s: %s", type(exc).__name__, exc)

            return LLMResult(reply_text, "LIVE_INFERENCE", str(response_model), elapsed_ms, input_tokens, output_tokens, entry.key_id, failed_attempts)

        except Exception as exc:
            failed_attempts += 1
            retryable = is_retryable_error(exc)
            logger.warning(
                "LLM call failed for %s (retryable=%s, attempt=%d/%d): %s: %s",
                entry.key_id, retryable, failed_attempts, len(key_pool), type(exc).__name__, exc,
            )
            continue

    raise AllProvidersUnavailableError("all providers unavailable")
