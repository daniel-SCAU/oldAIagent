import logging
import os
from typing import Any, Dict, List

import requests
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential
from . import resolve_contact_id

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

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
    """Send a normalized SMS message to the FastAPI service."""
    headers = {"X-API-KEY": API_KEY}

    url = f"{API_BASE}/webhook"

    try:
        _post_with_retry(url, msg, headers).raise_for_status()
    except Exception as exc:
        log.error("Failed forwarding SMS message: %s", exc)


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw Twilio message to the app's schema."""
    return {
        "sender": raw.get("from"),
        "app": "sms",
        "message": raw.get("body", ""),
        "conversation_id": raw.get("sid"),
    }


def fetch_messages() -> List[Dict[str, Any]]:
    """Retrieve messages from the Twilio REST API."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        log.warning("Twilio credentials not configured")
        return []
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    resp = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for item in resp.json().get("messages", []):
        out.append(_normalize(item))
    return out


def ingest() -> None:
    """Fetch and forward SMS messages."""
    for msg in fetch_messages():
        _forward(msg)


if __name__ == "__main__":
    ingest()
