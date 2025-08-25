import logging
import os
from typing import Any, Dict, List

import requests
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential
from . import resolve_contact_id

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
AULA_API_URL = os.getenv("AULA_API_URL")
AULA_TOKEN = os.getenv("AULA_TOKEN")

log = logging.getLogger(__name__)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(log, logging.WARNING),
)
def _post_with_retry(url: str, msg: Dict[str, Any], headers: Dict[str, str]):
    return requests.post(url, json=msg, headers=headers, timeout=10)


def _forward(msg: Dict[str, Any]) -> None:
    """Send a normalized Aula message to the FastAPI service."""
    headers = {"X-API-KEY": API_KEY}

    url = f"{API_BASE}/webhook"

    try:
        _post_with_retry(url, msg, headers).raise_for_status()
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
