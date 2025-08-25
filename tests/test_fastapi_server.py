import os
import sys
import pytest
from fastapi.testclient import TestClient
import sqlite3
import json
from contextlib import contextmanager

# Ensure the repository root is on sys.path for module imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import app

API_KEY = app.API_KEY_EXPECTED


class SQLiteCursor:
    def __init__(self, cur):
        self.cur = cur
        self.last_query = ""

    def execute(self, query, params=None):
        query = query.replace("%s", "?").replace("ILIKE", "LIKE")
        if params is None:
            params = []
        if "RETURNING" in query.upper():
            base, _ = query.rsplit("RETURNING", 1)
            self.cur.execute(base, params)
            last_id = self.cur.lastrowid
            if "chat" in base.lower():
                select = "SELECT id, conversation_id, created_at FROM Chat WHERE id = ?"
            elif "contacts" in base.lower():
                select = "SELECT id, name, info FROM contacts WHERE id = ?"
            else:
                select = (
                    "SELECT id, conversation_id, status, summary, created_at FROM summary_tasks WHERE id = ?"
                )
            self.last_query = select
            self.cur.execute(select, (last_id,))
            return self
        self.last_query = query
        self.cur.execute(query, params)
        return self

    def fetchone(self):
        row = self.cur.fetchone()
        if row is None:
            return None
        row = tuple(row)
        if "from contacts" in self.last_query.lower():
            return (row[0], row[1], json.loads(row[2]) if row[2] else None)
        return row

    def fetchall(self):
        rows = [tuple(r) for r in self.cur.fetchall()]
        if "from contacts" in self.last_query.lower():
            return [(r[0], r[1], json.loads(r[2]) if r[2] else None) for r in rows]
        return rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cur.close()


class SQLiteConnection:
    def __init__(self, conn):
        self.conn = conn

    def cursor(self):
        return SQLiteCursor(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()


@pytest.fixture
def client(monkeypatch):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE Chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            app TEXT,
            message TEXT,
            conversation_id TEXT,
            contact_id INTEGER,
            category TEXT,
            message_type TEXT,
            thread_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            info TEXT
        );
        CREATE TABLE summary_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE followup_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            task TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    @contextmanager
    def _db():
        try:
            yield SQLiteConnection(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    monkeypatch.setattr(app, "db", _db)
    monkeypatch.setattr(app, "init_db_pool", lambda: None)
    monkeypatch.setattr(app, "run_migrations", lambda: None)
    monkeypatch.setattr(app, "init_db_schema", lambda: None)

    class DummyScheduler:
        def start(self):
            pass

        def add_job(self, *args, **kwargs):
            pass

        def shutdown(self, wait=False):
            pass

    monkeypatch.setattr(app, "scheduler", DummyScheduler())

    with TestClient(app.app) as c:
        yield c
    conn.close()


class TestFastAPIServer:
    def test_message_creation_and_history(self, client):
        payload = {
            "sender": "alice",
            "app": "sms",
            "message": "Hello world",
            "conversation_id": "conv1",
        }
        resp = client.post("/messages", json=payload, headers={"X-API-KEY": API_KEY})
        assert resp.status_code == 200
        cid = resp.json()["conversation_id"]
        hist = client.get(
            f"/conversations/{cid}/messages", headers={"X-API-KEY": API_KEY}
        )
        assert hist.status_code == 200
        assert hist.json()[0]["message"] == "Hello world"

    def test_search_messages(self, client):
        payload = {
            "sender": "bob",
            "app": "email",
            "message": "Searching is fun",
            "conversation_id": "conv2",
        }
        client.post("/messages", json=payload, headers={"X-API-KEY": API_KEY})
        resp = client.get(
            "/search",
            params={"q": "Searching"},
            headers={"X-API-KEY": API_KEY},
        )
        assert resp.status_code == 200
        assert any("Searching" in m["message"] for m in resp.json())

    def test_contacts_endpoints(self, client):
        contact = {"name": "Charlie", "info": {"email": "c@example.com"}}
        resp = client.post("/contacts", json=contact, headers={"X-API-KEY": API_KEY})
        assert resp.status_code == 200
        list_resp = client.get("/contacts", headers={"X-API-KEY": API_KEY})
        assert list_resp.status_code == 200
        assert list_resp.json()[0]["info"]["email"] == "c@example.com"

    def test_summarization_flow(self, client):
        cid = "conv3"
        client.post(
            "/messages",
            json={"sender": "a", "app": "chat", "message": "Hello", "conversation_id": cid},
            headers={"X-API-KEY": API_KEY},
        )
        client.post(
            "/messages",
            json={"sender": "b", "app": "chat", "message": "How are you?", "conversation_id": cid},
            headers={"X-API-KEY": API_KEY},
        )
        task_resp = client.post(
            "/tasks", json={"conversation_id": cid}, headers={"X-API-KEY": API_KEY}
        )
        assert task_resp.status_code == 200
        task_id = task_resp.json()["id"]
        app.process_summary_tasks()
        get_resp = client.get(f"/tasks/{task_id}", headers={"X-API-KEY": API_KEY})
        assert get_resp.status_code == 200
        assert "Hello" in get_resp.json()["summary"]
