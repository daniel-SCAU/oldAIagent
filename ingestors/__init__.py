"""Ingestion helpers and platform connectors.

This package contains modules that fetch messages from external platforms and
forward them to the FastAPI ``POST /messages`` endpoint.  A small helper for
resolving contact IDs is provided so ingestors can attach a ``contact_id`` to
messages when the sender matches a stored contact.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

API_BASE = os.getenv("APP_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "dev-api-key")

log = logging.getLogger(__name__)


def resolve_contact_id(name: str) -> Optional[int]:
    """Return the contact ID matching ``name`` if one exists."""
    headers = {"X-API-KEY": API_KEY}
    try:
        resp = requests.get(f"{API_BASE}/contacts", headers=headers, timeout=5)
        resp.raise_for_status()
        for c in resp.json():
            if c.get("name") == name:
                return c.get("id")
    except Exception as exc:  # pragma: no cover - network errors
        log.error("Contact lookup failed for %s: %s", name, exc)
    return None

