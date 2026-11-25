"""Tests for POST /chat validation, metadata contract, and error handling."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import litellm


def _fake_model_response(
    content: str = "The capital of France is Paris.",
    *,
    model: str = "openai/gpt-4o-mini",
    prompt_tokens: int = 42,
    completion_tokens: int = 9,
    cache_hit: bool = False,
):
    return SimpleNamespace(
        model=model,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
        _hidden_params={"cache_hit": cache_hit},
    )


def test_chat_validation_missing_session_id(client) -> None:
    resp = client.post("/chat", json={"message": "Hello"})
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_chat_validation_empty_and_long_session_id(client) -> None:
    r1 = client.post("/chat", json={"session_id": "", "message": "Hello"})
    assert r1.status_code == 422
    assert "detail" in r1.json()

    r2 = client.post("/chat", json={"session_id": "x" * 129, "message": "Hello"})
    assert r2.status_code == 422
    assert "detail" in r2.json()


def test_chat_validation_whitespace_and_over_4000_message(client) -> None:
    r1 = client.post("/chat", json={"session_id": "s-val-1", "message": "   \n\t  "})
    assert r1.status_code == 422
    assert "detail" in r1.json()

    r2 = client.post("/chat", json={"session_id": "s-val-1", "message": "a" * 4001})
    assert r2.status_code == 422
    assert "detail" in r2.json()

    # Failed 422 requests must NOT create session history
    hist = client.get("/sessions/s-val-1/messages")
    assert hist.status_code == 404


def test_chat_validation_malformed_json(client) -> None:
    resp = client.post(
        "/chat",
        content="{not-valid-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert "detail" in resp.json()


def test_chat_accepts_exact_4000_chars_and_trims_whitespace(client, monkeypatch) -> None:
    captured_messages = []

    async def fake_acompletion(**kwargs):
        captured_messages.append(kwargs["messages"])
        return _fake_model_response("Accepted.")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    exact_4000 = "  " + ("z" * 4000) + "  "
    resp = client.post("/chat", json={"session_id": "s-4000", "message": exact_4000})
    assert resp.status_code == 200
    assert captured_messages[0][-1]["content"] == "z" * 4000


def test_chat_response_and_metadata_contract(client, monkeypatch) -> None:
    monkeypatch.setattr(
        litellm,
        "acompletion",
        AsyncMock(return_value=_fake_model_response("Paris.", prompt_tokens=42, completion_tokens=9)),
    )

    resp = client.post(
        "/chat",
        json={"session_id": "s-contract", "message": "What is the capital of France?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "s-contract"
    assert data["reply"] == "Paris."

    meta = data["metadata"]
    assert set(meta.keys()) == {
        "resolution_source",
        "model",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "key_id",
        "fallback_attempts",
    }
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == "openai/gpt-4o-mini"
    assert isinstance(meta["latency_ms"], int)
    assert meta["input_tokens"] == 42
    assert meta["output_tokens"] == 9
    assert meta["key_id"] == "key_1"
    assert meta["fallback_attempts"] == 0
    assert "test-secret-key" not in resp.text


def test_chat_empty_provider_response_fails_over_or_503(client, monkeypatch) -> None:
    empty_resp = _fake_model_response("   ")
    monkeypatch.setattr(litellm, "acompletion", AsyncMock(return_value=empty_resp))

    resp = client.post("/chat", json={"session_id": "s-empty", "message": "Hello"})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "all providers unavailable"}
    assert client.get("/sessions/s-empty/messages").status_code == 404
