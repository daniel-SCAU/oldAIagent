import importlib
from fastapi.testclient import TestClient
import app


def test_missing_pool_returns_503(monkeypatch):
    """Endpoints should return 503 when the DB pool is missing."""
    # Prevent startup from trying to init the DB or scheduler
    monkeypatch.setattr(app, "init_db_pool", lambda: None)
    monkeypatch.setattr(app, "run_migrations", lambda: None)
    monkeypatch.setattr(app.scheduler, "start", lambda *a, **k: None)
    monkeypatch.setattr(app.scheduler, "add_job", lambda *a, **k: None)

    app.pool = None
    client = TestClient(app.app)
    resp = client.get("/contacts", headers={"X-API-Key": app.API_KEY_EXPECTED})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "Database unavailable"}
