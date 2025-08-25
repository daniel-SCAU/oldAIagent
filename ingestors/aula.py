import logging
import os
from typing import Any, Dict, List

import requests

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
AULA_API_URL = os.getenv("AULA_API_URL")
AULA_TOKEN = os.getenv("AULA_TOKEN")

log = logging.getLogger(__name__)


def _forward(msg: Dict[str, Any]) -> None:
    """Send a normalized Aula message to the FastAPI service."""
    headers = {"X-API-KEY": API_KEY}
    url = f"{API_BASE}/webhook"
    try:
        requests.post(url, json=msg, headers=headers, timeout=10).raise_for_status()
    except Exception as exc:
        log.error("Failed forwarding Aula message: %s", exc)


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw Aula message to the app's schema."""
    return {
        "sender": raw.get("sender", "unknown"),
        "app": "aula",
        "message": raw.get("message", ""),
        "conversation_id": raw.get("conversation_id"),
    }


def fetch_messages() -> List[Dict[str, Any]]:
    """Fetch messages from the Aula REST API."""
    if not AULA_API_URL or not AULA_TOKEN:
        log.warning("Aula API not configured")
        return []
    headers = {"Authorization": f"Bearer {AULA_TOKEN}"}
    resp = requests.get(f"{AULA_API_URL}/messages", headers=headers, timeout=10)
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for item in resp.json().get("messages", []):
        out.append(_normalize(item))
    return out


def ingest() -> None:
    """Fetch and forward Aula messages."""
    for msg in fetch_messages():
        _forward(msg)


if __name__ == "__main__":
    ingest()
