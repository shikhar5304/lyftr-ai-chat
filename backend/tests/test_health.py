"""Tests for GET /health."""

from __future__ import annotations


def test_health_ok_with_two_keys(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "keys_configured": 2,
        "cache_enabled": True,
    }


def test_health_reports_actual_key_count(make_client) -> None:
    tc = make_client(api_keys="k1,k2,k3", cache_enabled="false")
    resp = tc.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "keys_configured": 3,
        "cache_enabled": False,
    }


def test_health_returns_503_when_no_keys_configured(make_client) -> None:
    tc = make_client(api_keys="")
    resp = tc.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert "detail" in body


def test_health_returns_503_when_database_unreachable(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.health.check_db_health", lambda _path: False)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json() == {"detail": "database unavailable"}
