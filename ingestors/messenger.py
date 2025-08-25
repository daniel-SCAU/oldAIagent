import logging
import os
from typing import Any, Dict, List

import requests
from . import resolve_contact_id

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")
MESSENGER_PAGE_ID = os.getenv("MESSENGER_PAGE_ID")
MESSENGER_PAGE_TOKEN = os.getenv("MESSENGER_PAGE_TOKEN")

log = logging.getLogger(__name__)


def _forward(msg: Dict[str, Any]) -> None:
    """Send a normalized message to the FastAPI service."""
    headers = {"X-API-KEY": API_KEY}
    url = f"{API_BASE}/messages"
    cid = resolve_contact_id(msg.get("sender", ""))
    if cid is not None:
        msg["contact_id"] = cid
    try:
        requests.post(url, json=msg, headers=headers, timeout=10).raise_for_status()
    except Exception as exc:
        log.error("Failed forwarding Messenger message: %s", exc)


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw Messenger message to the app's schema."""
    return {
        "sender": raw.get("from", {}).get("id", "unknown"),
        "app": "messenger",
        "message": raw.get("message", ""),
        "conversation_id": raw.get("id"),
    }


def fetch_messages() -> List[Dict[str, Any]]:
    """Retrieve messages from the Facebook Graph API."""
    if not MESSENGER_PAGE_TOKEN or not MESSENGER_PAGE_ID:
        log.warning("Messenger credentials not configured")
        return []
    url = (
        f"https://graph.facebook.com/v17.0/{MESSENGER_PAGE_ID}/conversations"
        f"?access_token={MESSENGER_PAGE_TOKEN}"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    out: List[Dict[str, Any]] = []
    for conv in resp.json().get("data", []):
        thread_id = conv["id"]
        m_url = (
            f"https://graph.facebook.com/v17.0/{thread_id}/messages"
            f"?access_token={MESSENGER_PAGE_TOKEN}"
        )
        m_resp = requests.get(m_url, timeout=10)
        m_resp.raise_for_status()
        for msg in m_resp.json().get("data", []):
            if "message" in msg:
                out.append(_normalize(msg))
    return out


def ingest() -> None:
    """Fetch and forward any new Messenger messages."""
    for msg in fetch_messages():
        _forward(msg)


if __name__ == "__main__":
    ingest()
