"""Tests for automatic key failover and X-Simulate-Failure header."""

from __future__ import annotations

from types import SimpleNamespace

import litellm


def _ok_response(content: str = "Recovered reply."):
    return SimpleNamespace(
        model="openai/gpt-4o-mini",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=5),
        _hidden_params={"cache_hit": False},
    )


def test_simulate_failure_429_falls_back_to_key_2(client, monkeypatch) -> None:
    seen_keys: list[str] = []

    async def fake_acompletion(**kwargs):
        seen_keys.append(kwargs["api_key"])
        return _ok_response("Fallback via key_2")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    resp = client.post(
        "/chat",
        json={"session_id": "s-sim-429", "message": "Hello"},
        headers={"X-Simulate-Failure": "key_1=429"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "Fallback via key_2"
    assert body["metadata"]["key_id"] == "key_2"
    assert body["metadata"]["fallback_attempts"] == 1
    assert body["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert seen_keys == ["test-secret-key-two"]


def test_simulate_failure_500_and_502_fall_back_to_key_2(client, monkeypatch) -> None:
    async def fake_acompletion(**kwargs):
        return _ok_response(f"Used {kwargs['api_key']}")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    for status_code in (500, 502):
        resp = client.post(
            "/chat",
            json={"session_id": f"s-sim-{status_code}", "message": "Test"},
            headers={"X-Simulate-Failure": f"key_1={status_code}"},
        )
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert meta["key_id"] == "key_2"
        assert meta["fallback_attempts"] == 1


def test_simulate_failure_wildcard_returns_503_and_does_not_persist(client, monkeypatch) -> None:
    async def should_not_be_called(**_kwargs):
        raise AssertionError("Provider should not be called when *=429 is simulated")

    monkeypatch.setattr(litellm, "acompletion", should_not_be_called)

    resp = client.post(
        "/chat",
        json={"session_id": "s-all-fail", "message": "Should fail"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 503
    assert resp.json() == {"detail": "all providers unavailable"}

    hist = client.get("/sessions/s-all-fail/messages")
    assert hist.status_code == 404
    assert hist.json() == {"detail": "session not found"}


def test_simulate_failure_disabled_ignores_header(make_client, monkeypatch) -> None:
    tc = make_client(enable_failure_simulation="false")

    async def fake_acompletion(**_kwargs):
        return _ok_response("Normal key_1 response")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    resp = tc.post(
        "/chat",
        json={"session_id": "s-sim-off", "message": "Hello"},
        headers={"X-Simulate-Failure": "*=429"},
    )
    assert resp.status_code == 200
    assert resp.json()["metadata"]["key_id"] == "key_1"
    assert resp.json()["metadata"]["fallback_attempts"] == 0


def test_real_provider_429_and_5xx_failover(client, monkeypatch) -> None:
    calls = {"count": 0}

    async def fake_acompletion(**kwargs):
        calls["count"] += 1
        if kwargs["api_key"] == "test-secret-key-one":
            raise litellm.exceptions.RateLimitError(
                message="quota exceeded",
                llm_provider="openai",
                model="openai/gpt-4o-mini",
            )
        return _ok_response("Recovered from real 429")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    resp = client.post("/chat", json={"session_id": "s-real-429", "message": "Ping"})
    assert resp.status_code == 200
    assert calls["count"] == 2
    assert resp.json()["metadata"]["key_id"] == "key_2"
    assert resp.json()["metadata"]["fallback_attempts"] == 1


def test_single_key_failure_returns_503_safely(make_client, monkeypatch) -> None:
    tc = make_client(api_keys="only-one-key")

    async def fake_acompletion(**_kwargs):
        raise RuntimeError("unexpected internal boom with secret only-one-key")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    resp = tc.post("/chat", json={"session_id": "s-single", "message": "Hello"})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "all providers unavailable"}
    assert "only-one-key" not in resp.text
    assert "Traceback" not in resp.text
