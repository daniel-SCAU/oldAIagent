import importlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

# Ensure root directory is on sys.path for module imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def reload_server(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("MYGPT_API_URL", "http://example.com")
    monkeypatch.setenv("MYGPT_API_KEY", "test-api-key")
    import server
    importlib.reload(server)
    return server


class DummyResponse:
    def json(self):
        return {"response": "dummy"}

    def raise_for_status(self):
        pass


def test_concurrent_test_response(monkeypatch):
    server = reload_server(monkeypatch)
    # Avoid real HTTP calls
    monkeypatch.setattr(server.requests, "post", lambda *args, **kwargs: DummyResponse())

    headers = {"X-API-KEY": "test-key"}

    def send_request(i):
        with server.app.test_client() as client:
            resp = client.post(
                "/test-response",
                json={"prompt": f"hello {i}"},
                headers=headers,
            )
            assert resp.status_code == 200

    count = 20
    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(send_request, range(count)))

    assert server.store.response_count() == min(count, 10)
    assert len(server.store.get_responses()) == min(count, 10)
