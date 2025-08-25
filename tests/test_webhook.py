import os
import sys
from contextlib import contextmanager
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app
from fastapi.testclient import TestClient


class FakeCursor:
    def __init__(self, data):
        self.data = data
        self.fetchone_result = None

    def execute(self, sql, params=None):
        sql = sql.strip().lower()
        if sql.startswith("insert into chat"):
            _id = len(self.data["Chat"]) + 1
            sender, app_name, message, conv_id = params
            self.data["Chat"].append({
                "id": _id,
                "conversation_id": conv_id,
                "sender": sender,
                "app": app_name,
                "message": message,
            })
            self.fetchone_result = (_id, conv_id, datetime.utcnow())

    def fetchone(self):
        return self.fetchone_result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class FakeConnection:
    def __init__(self, data):
        self.data = data

    def cursor(self):
        return FakeCursor(self.data)

    def commit(self):
        pass

    def rollback(self):
        pass


@contextmanager
def fake_db(data):
    yield FakeConnection(data)


def test_webhook_persists_message(monkeypatch):
    data = {"Chat": []}

    def _fake_db():
        return fake_db(data)

    monkeypatch.setattr(app, "db", _fake_db)
    client = TestClient(app.app)
    payload = {
        "sender": "alice",
        "app": "sms",
        "message": "hello",
        "conversation_id": "1",
    }
    resp = client.post("/webhook", json=payload, headers={"X-API-Key": app.API_KEY_EXPECTED})
    assert resp.status_code == 200
    assert resp.json()["id"] == 1
    assert len(data["Chat"]) == 1
    assert data["Chat"][0]["message"] == "hello"
