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
        self.fetchall_result = None

    def execute(self, sql, params=None):
        sql_l = sql.strip().lower()
        self.data["last_sql"] = sql_l
        if sql_l.startswith("select exists"):
            self.fetchone_result = (self.data.get("has_search_vector", False),)
        elif "search_vector @@ to_tsquery" in sql_l:
            tokens = params[0].split(" & ")
            candidate_sets = [self.data["index"].get(t, set()) for t in tokens]
            if candidate_sets:
                id_set = set.intersection(*candidate_sets)
            else:
                id_set = set()
            rows = [self.data["rows_by_id"][i] for i in sorted(id_set)]
            self.data["scan_count"] = sum(len(self.data["index"].get(t, set())) for t in tokens)
            self.fetchall_result = [
                (
                    r["id"],
                    r["conversation_id"],
                    r["sender"],
                    r["app"],
                    r["message"],
                    r["created_at"],
                    r["contact_id"],
                    r["message_type"],
                    r["thread_key"],
                )
                for r in rows
            ]
        elif "message ilike" in sql_l:
            pattern = params[0].strip("%").lower()
            rows = []
            self.data["scan_count"] = 0
            for r in self.data["Chat"]:
                self.data["scan_count"] += 1
                if pattern in r["message"].lower():
                    rows.append(r)
            self.fetchall_result = [
                (
                    r["id"],
                    r["conversation_id"],
                    r["sender"],
                    r["app"],
                    r["message"],
                    r["created_at"],
                    r["contact_id"],
                    r["message_type"],
                    r["thread_key"],
                )
                for r in rows
            ]

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result

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


def build_data(messages, has_search_vector=True):
    chat_rows = []
    index = {}
    rows_by_id = {}
    for idx, msg in enumerate(messages, 1):
        row = {
            "id": idx,
            "conversation_id": str(idx),
            "sender": "user",
            "app": "sms",
            "message": msg,
            "created_at": datetime.utcnow(),
            "contact_id": None,
            "message_type": None,
            "thread_key": None,
        }
        rows_by_id[idx] = row
        tokens = set(msg.lower().split())
        for t in tokens:
            index.setdefault(t, set()).add(idx)
        chat_rows.append(row)
    return {
        "Chat": chat_rows,
        "index": index,
        "rows_by_id": rows_by_id,
        "has_search_vector": has_search_vector,
        "last_sql": "",
        "scan_count": 0,
    }


def make_client(monkeypatch, data):
    def _fake_db():
        return fake_db(data)

    monkeypatch.setattr(app, "db", _fake_db)
    return TestClient(app.app)


def test_search_uses_tsvector(monkeypatch):
    data = build_data(["hello world", "another message"], has_search_vector=True)
    client = make_client(monkeypatch, data)
    resp = client.get("/search", params={"q": "hello"}, headers={"X-API-Key": app.API_KEY_EXPECTED})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["message"] == "hello world"
    assert "search_vector @@ to_tsquery" in data["last_sql"]


def test_search_falls_back_to_ilike(monkeypatch):
    data = build_data(["hello world", "another message"], has_search_vector=False)
    client = make_client(monkeypatch, data)
    resp = client.get("/search", params={"q": "hello"}, headers={"X-API-Key": app.API_KEY_EXPECTED})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert "message ilike" in data["last_sql"]


def test_search_vector_scans_fewer_rows(monkeypatch):
    messages = ["noise" for _ in range(50)] + ["unique term here"] + ["more noise" for _ in range(50)]
    data_ts = build_data(messages, has_search_vector=True)
    client = make_client(monkeypatch, data_ts)
    resp = client.get("/search", params={"q": "unique"}, headers={"X-API-Key": app.API_KEY_EXPECTED})
    assert resp.status_code == 200
    scan_ts = data_ts["scan_count"]

    data_ilike = build_data(messages, has_search_vector=False)
    client = make_client(monkeypatch, data_ilike)
    resp = client.get("/search", params={"q": "unique"}, headers={"X-API-Key": app.API_KEY_EXPECTED})
    assert resp.status_code == 200
    scan_ilike = data_ilike["scan_count"]

    assert scan_ts < scan_ilike
