import logging
import os
from typing import Any, Dict, List

import requests
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential
from . import resolve_contact_id

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

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
    """Send a normalized WhatsApp message to the FastAPI service."""
    headers = {"X-API-KEY": API_KEY}

    url = f"{API_BASE}/webhook"

    try:
        _post_with_retry(url, msg, headers).raise_for_status()
    except Exception as exc:
        log.error("Failed forwarding WhatsApp message: %s", exc)


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw WhatsApp message to the app's schema."""
    return {
        "sender": raw.get("from"),
        "app": "whatsapp",
        "message": raw.get("text", {}).get("body", ""),
        "conversation_id": raw.get("id"),
    }


def handle_webhook(payload: Dict[str, Any]) -> None:
    """Process an incoming WhatsApp webhook payload."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                _forward(_normalize(message))


def fetch_messages() -> List[Dict[str, Any]]:
    """Optionally poll the API for messages (useful for testing)."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        log.warning("WhatsApp credentials not configured")
        return []
    url = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for msg in resp.json().get("data", []):
        out.append(_normalize(msg))
    return out


def ingest() -> None:
    for msg in fetch_messages():
        _forward(msg)


if __name__ == "__main__":
    ingest()
