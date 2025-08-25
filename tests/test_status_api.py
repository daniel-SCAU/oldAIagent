import importlib

import pytest


def reload_server(monkeypatch):
    """Reload server module with a known API key."""
    monkeypatch.setenv("API_KEY", "test-key")
    import server
    importlib.reload(server)
    return server


def test_status_requires_correct_api_key(monkeypatch):
    server = reload_server(monkeypatch)
    client = server.app.test_client()

    # Correct key should allow access
    ok = client.get("/status", headers={"X-API-KEY": "test-key"})
    assert ok.status_code == 200

    # Incorrect key should be rejected
    bad = client.get("/status", headers={"X-API-KEY": "wrong"})
    assert bad.status_code == 401
