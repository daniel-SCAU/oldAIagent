from contextlib import contextmanager

import app


def test_long_conversation_summary(monkeypatch):
    messages = [
        {"sender": "User", "message": f"Message {i}"} for i in range(20)
    ]
    messages[0]["message"] = "We need to finish the project"
    messages[10]["message"] = "The deadline is Friday"
    messages[-1]["message"] = "Let's prepare a presentation"

    class FakeAPI:
        def generate_test_response(self, prompt: str):
            assert "We need to finish the project" in prompt
            assert "The deadline is Friday" in prompt
            assert "Let's prepare a presentation" in prompt
            return {
                "response": "Project needs completion with deadline Friday and a presentation planned."
            }

    monkeypatch.setattr(app, "myGPTAPI", FakeAPI)
    summary = app.summarize_messages(messages)
    assert "project" in summary.lower()
    assert "deadline" in summary.lower()
    assert "presentation" in summary.lower()


def test_summarize_conversation_api_error(monkeypatch):
    data = {
        "Chat": [
            {"id": 1, "conversation_id": "1", "sender": "A", "message": "Hello"},
            {"id": 2, "conversation_id": "1", "sender": "B", "message": "Bye"},
        ]
    }

    class ErrorAPI:
        def generate_test_response(self, prompt: str):
            raise RuntimeError("boom")

    class Cursor:
        def __init__(self, data):
            self.data = data
        def execute(self, sql, params=None):
            conv_id = params[0]
            self.result = [
                (m["sender"], m["message"])
                for m in self.data["Chat"]
                if m["conversation_id"] == conv_id
            ]
        def fetchall(self):
            return self.result
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            pass

    class Conn:
        def __init__(self, data):
            self.data = data
        def cursor(self):
            return Cursor(self.data)
        def commit(self):
            pass
        def rollback(self):
            pass

    @contextmanager
    def fake_db(data):
        yield Conn(data)

    monkeypatch.setattr(app, "db", lambda: fake_db(data))
    monkeypatch.setattr(app, "myGPTAPI", ErrorAPI)
    summary = app.summarize_conversation("1")
    assert summary == "Hello ... Bye"

