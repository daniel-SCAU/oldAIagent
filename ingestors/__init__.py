"""Ingestion modules for external messaging platforms.

Modules include connectors for Messenger, WhatsApp, Outlook, SMS and Aula.
Each module exposes a ``fetch_messages`` helper and an ``ingest`` function
that forwards normalized messages to the FastAPI service.
"""
