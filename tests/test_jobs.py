import os
import sys
from contextlib import contextmanager

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app


def test_categorize_message():
    meta = app.categorize_message("Is this working?")
    assert meta["intent"] == "question"
    assert meta["sentiment"] == "neutral"
    meta = app.categorize_message("Please review the code")
    assert meta["intent"] == "task"
    meta = app.categorize_message("I love this")
    assert meta["sentiment"] == "positive"
    meta = app.categorize_message("This is terrible")
    assert meta["sentiment"] == "negative"


def test_summarize_messages(monkeypatch):
    msgs = ["Hello", "How are you?", "Goodbye"]

    class FakeAPI:
        def generate_test_response(self, prompt: str):
            return {
                "response": "A friendly greeting and inquiry about well-being followed by a farewell."
            }

    monkeypatch.setattr(app, "myGPTAPI", FakeAPI)
    summary = app.summarize_messages(msgs)
    assert summary == "A friendly greeting and inquiry about well-being followed by a farewell."
    assert summary != "Hello ... Goodbye"


class FakeCursor:
    def __init__(self, data):
        self.data = data
        self.result = []

    def execute(self, sql, params=None):
        sql = sql.strip().lower()
        if sql.startswith("select id, conversation_id from summary_tasks"):
            self.result = [
                (t["id"], t["conversation_id"])
                for t in self.data["summary_tasks"]
                if t["status"] == "pending"
            ]
        elif sql.startswith("select message from chat"):
            conv_id = params[0]
            self.result = [
                (m["message"],) for m in self.data["Chat"] if m["conversation_id"] == conv_id
            ]
        elif sql.startswith("update summary_tasks set summary"):
            summary, tid = params
            for t in self.data["summary_tasks"]:
                if t["id"] == tid:
                    t["summary"] = summary
                    t["status"] = "completed"
        elif sql.startswith("update summary_tasks set status='failed'"):
            tid = params[0]
            for t in self.data["summary_tasks"]:
                if t["id"] == tid:
                    t["status"] = "failed"

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


def test_process_new_messages(monkeypatch):
    data = {"Chat": [
        {"id": 1, "message": "Can you help me?", "intent": None, "sentiment": None},
        {"id": 2, "message": "I hate bugs", "intent": None, "sentiment": None},
    ]}

    class ClassifyCursor:
        def __init__(self, data):
            self.data = data
            self.result = []

        def execute(self, sql, params=None):
            sql = sql.strip().lower()
            if sql.startswith("select id, message from chat where intent is null"):
                self.result = [
                    (m["id"], m["message"])
                    for m in self.data["Chat"]
                    if m.get("intent") is None or m.get("sentiment") is None
                ][:50]
            elif sql.startswith("update chat set intent"):
                intent, sentiment, category, mid = params
                for m in self.data["Chat"]:
                    if m["id"] == mid:
                        m["intent"] = intent
                        m["sentiment"] = sentiment
                        m["category"] = category

        def fetchall(self):
            return self.result

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    class ClassifyConnection:
        def __init__(self, data):
            self.data = data

        def cursor(self):
            return ClassifyCursor(self.data)

        def commit(self):
            pass

        def rollback(self):
            pass

    @contextmanager
    def fake_db_local(data):
        yield ClassifyConnection(data)

    monkeypatch.setattr(app, "db", lambda: fake_db_local(data))
    app.process_new_messages()
    assert data["Chat"][0]["intent"] == "question"
    assert data["Chat"][1]["sentiment"] == "negative"


def test_process_summary_tasks(monkeypatch):
    data = {
        "Chat": [
            {"id": 1, "conversation_id": "1", "message": "Hello"},
            {"id": 2, "conversation_id": "1", "message": "How are you?"},
        ],
        "summary_tasks": [
            {"id": 1, "conversation_id": "1", "status": "pending", "summary": None}
        ],
    }

    def _fake_db():
        return fake_db(data)

    class FakeAPI:
        def generate_test_response(self, prompt: str):
            return {"response": "Hello and a check-in before goodbye."}

    monkeypatch.setattr(app, "db", _fake_db)
    monkeypatch.setattr(app, "myGPTAPI", FakeAPI)
    app.process_summary_tasks()
    task = data["summary_tasks"][0]
    assert task["status"] == "completed"
    assert task["summary"] == "Hello and a check-in before goodbye."
    assert task["summary"] != "Hello ... How are you?"

