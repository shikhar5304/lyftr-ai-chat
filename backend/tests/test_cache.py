"""Tests for LiteLLM response cache behavior and cache metadata contract."""

from __future__ import annotations

import litellm
from litellm.types.utils import Choices, Message, ModelResponse, Usage


def test_cache_hit_and_miss_via_litellm_cache(client, monkeypatch) -> None:
    """Verify LiteLLM's built-in Cache keys on model + full messages and reports LLM_CACHE."""
    assert litellm.cache is not None
    provider_calls = 0

    async def fake_acompletion(**kwargs):
        nonlocal provider_calls
        cache_obj = litellm.cache
        cache_arg = kwargs.get("cache") or {}
        use_cache = bool(kwargs.get("caching", False)) and bool(cache_arg.get("use-cache", False))
        if use_cache and cache_obj is not None:
            cached = await cache_obj.async_get_cache(
                model=kwargs["model"],
                messages=kwargs["messages"],
                cache=cache_arg,
            )
            if cached is not None:
                if isinstance(cached, dict):
                    restored = ModelResponse(**cached)
                else:
                    restored = cached
                restored._hidden_params = {"cache_hit": True}
                return restored

        provider_calls += 1
        resp = ModelResponse(
            id=f"chatcmpl-test-{provider_calls}",
            model=kwargs["model"],
            choices=[
                Choices(
                    index=0,
                    finish_reason="stop",
                    message=Message(
                        role="assistant",
                        content="The capital of France is Paris."
                        if "France" in kwargs["messages"][-1]["content"]
                        else "The capital of Germany is Berlin.",
                    ),
                )
            ],
            usage=Usage(prompt_tokens=31, completion_tokens=8, total_tokens=39),
        )
        resp._hidden_params = {"cache_hit": False}

        if use_cache and cache_obj is not None:
            await cache_obj.async_add_cache(
                resp,
                model=kwargs["model"],
                messages=kwargs["messages"],
                cache=cache_arg,
            )
        return resp

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    # First fresh session -> LIVE_INFERENCE
    r1 = client.post(
        "/chat",
        json={"session_id": "cache-test-a", "message": "What is the capital of France?"},
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert d1["metadata"]["key_id"] == "key_1"
    assert d1["metadata"]["fallback_attempts"] == 0
    assert d1["metadata"]["input_tokens"] == 31
    assert d1["metadata"]["output_tokens"] == 8

    # Second fresh session with identical message -> LLM_CACHE
    r2 = client.post(
        "/chat",
        json={"session_id": "cache-test-b", "message": "What is the capital of France?"},
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["reply"] == d1["reply"]
    assert d2["metadata"]["resolution_source"] == "LLM_CACHE"
    assert d2["metadata"]["key_id"] is None
    assert d2["metadata"]["fallback_attempts"] == 0
    assert d2["metadata"]["input_tokens"] == 31
    assert d2["metadata"]["output_tokens"] == 8
    assert provider_calls == 1

    # Different message -> must NOT hit previous cache
    r3 = client.post(
        "/chat",
        json={"session_id": "cache-test-c", "message": "What is the capital of Germany?"},
    )
    assert r3.status_code == 200
    assert r3.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert provider_calls == 2

    # Simulated failure bypasses cache read and exercises key failover
    r4 = client.post(
        "/chat",
        json={"session_id": "cache-test-d", "message": "What is the capital of France?"},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert r4.status_code == 200
    assert r4.json()["metadata"]["key_id"] == "key_2"
    assert r4.json()["metadata"]["fallback_attempts"] == 1
