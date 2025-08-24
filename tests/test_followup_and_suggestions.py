import os
import sys
from contextlib import contextmanager

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app
from fastapi.testclient import TestClient


def test_detect_followup_tasks():
    text = "Please review the report and send feedback."
    tasks = app.detect_followup_tasks(text)
    assert any("review" in t.lower() for t in tasks)


class FakeCursor:
    def __init__(self, data):
        self.data = data
        self.fetchone_result = None
        self.result = []

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
            self.fetchone_result = (_id, conv_id, "now")
        elif sql.startswith("insert into followup_tasks"):
            conv_id, task = params
            self.data["followup_tasks"].append({"conversation_id": conv_id, "task": task})
        elif sql.startswith("select sender, message from chat"):
            conv_id = params[0]
            self.result = [
                (m["sender"], m["message"]) for m in self.data["Chat"] if m["conversation_id"] == conv_id
            ]
        else:
            self.result = []

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.result

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


def test_create_message_stores_tasks(monkeypatch):
    data = {"Chat": [], "followup_tasks": []}

    def _fake_db():
        return fake_db(data)

    monkeypatch.setattr(app, "db", _fake_db)
    msg = app.MessageIn(sender="alice", app="sms", message="Please call Bob", conversation_id="1")
    app.create_message(msg)
    assert len(data["followup_tasks"]) == 1
    assert "call" in data["followup_tasks"][0]["task"].lower()


def test_suggestions_endpoint(monkeypatch):
    data = {
        "Chat": [
            {"id": 1, "conversation_id": "1", "sender": "alice", "message": "Hello"},
            {"id": 2, "conversation_id": "1", "sender": "bob", "message": "Hi"},
        ],
        "followup_tasks": [],
    }

    def _fake_db():
        return fake_db(data)

    monkeypatch.setattr(app, "db", _fake_db)

    class FakeAPI:
        def generate_test_response(self, prompt: str):
            return {"response": "Sure\nLet's do it\nNo thanks"}

    monkeypatch.setattr(app, "myGPTAPI", FakeAPI)

    client = TestClient(app.app)
    resp = client.post(
        "/suggestions",
        json={"conversation_id": "1"},
        headers={"X-API-Key": app.API_KEY_EXPECTED},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggestions"][0].startswith("Sure")
