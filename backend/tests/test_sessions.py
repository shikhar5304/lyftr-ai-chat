"""Tests for multi-turn session persistence, isolation, and history ordering."""

from __future__ import annotations

from types import SimpleNamespace

import litellm


def test_unknown_session_returns_404(client) -> None:
    resp = client.get("/sessions/nonexistent-session/messages")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "session not found"}


def test_multiturn_persistence_oldest_first_and_isolation(client, monkeypatch) -> None:
    seen_histories: list[list[dict[str, str]]] = []

    async def fake_acompletion(**kwargs):
        seen_histories.append(list(kwargs["messages"]))
        last_user = kwargs["messages"][-1]["content"]
        if "favorite" in last_user and "Python" in last_user:
            reply = "Noted, Python is great."
        elif "What programming language" in last_user:
            has_python = any("Python" in m["content"] for m in kwargs["messages"])
            reply = "You said Python." if has_python else "I do not know."
        else:
            reply = "Isolated response."
        return SimpleNamespace(
            model="openai/gpt-4o-mini",
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))],
            usage=SimpleNamespace(
                prompt_tokens=sum(len(m["content"]) for m in kwargs["messages"]),
                completion_tokens=len(reply),
            ),
            _hidden_params={"cache_hit": False},
        )

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)

    r1 = client.post(
        "/chat",
        json={
            "session_id": "context-test",
            "message": "My favorite programming language is Python.",
            "system_prompt": "Be concise.",
        },
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/chat",
        json={
            "session_id": "context-test",
            "message": "What programming language did I say was my favorite?",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["reply"] == "You said Python."

    # Verify turn 2 rebuilt system prompt + turn 1 user + turn 1 assistant + turn 2 user
    assert seen_histories[1] == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "My favorite programming language is Python."},
        {"role": "assistant", "content": "Noted, Python is great."},
        {"role": "user", "content": "What programming language did I say was my favorite?"},
    ]

    # Different session must stay isolated
    r_other = client.post(
        "/chat",
        json={
            "session_id": "other-session",
            "message": "What programming language did I say was my favorite?",
        },
    )
    assert r_other.status_code == 200
    assert r_other.json()["reply"] == "I do not know."

    # History endpoint returns oldest-first and excludes system prompt
    hist_resp = client.get("/sessions/context-test/messages")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["session_id"] == "context-test"
    roles = [m["role"] for m in hist["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert all(m["role"] != "system" for m in hist["messages"])
    assert "metadata" not in hist["messages"][0]
    assert hist["messages"][1]["metadata"]["resolution_source"] == "LIVE_INFERENCE"
