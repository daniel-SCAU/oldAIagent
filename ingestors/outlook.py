import logging
import os
from typing import Any, Dict, List

import requests
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential
from . import resolve_contact_id

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
OUTLOOK_TOKEN = os.getenv("OUTLOOK_TOKEN")
OUTLOOK_USER_ID = os.getenv("OUTLOOK_USER_ID", "me")

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
    """Send a normalized Outlook message to the FastAPI service."""
    headers = {"X-API-KEY": API_KEY}

    url = f"{API_BASE}/webhook"

    try:
        _post_with_retry(url, msg, headers).raise_for_status()
    except Exception as exc:
        log.error("Failed forwarding Outlook message: %s", exc)


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw Outlook message to the app's schema."""
    sender = (
        raw.get("from", {})
        .get("emailAddress", {})
        .get("address", "unknown")
    )
    return {
        "sender": sender,
        "app": "outlook",
        "message": raw.get("subject", ""),
        "conversation_id": raw.get("conversationId"),
    }


def fetch_messages() -> List[Dict[str, Any]]:
    """Retrieve recent messages from the Microsoft Graph API."""
    if not OUTLOOK_TOKEN:
        log.warning("Outlook token not configured")
        return []
    url = f"https://graph.microsoft.com/v1.0/users/{OUTLOOK_USER_ID}/messages"
    headers = {"Authorization": f"Bearer {OUTLOOK_TOKEN}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for item in resp.json().get("value", []):
        out.append(_normalize(item))
    return out


def ingest() -> None:
    """Fetch and forward any new Outlook messages."""
    for msg in fetch_messages():
        _forward(msg)


if __name__ == "__main__":
    ingest()
