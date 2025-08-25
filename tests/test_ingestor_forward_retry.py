import importlib
import logging
from unittest.mock import MagicMock

import pytest
import requests


@pytest.mark.parametrize(
    "module_name, app_name",
    [
        ("ingestors.messenger", "Messenger"),
        ("ingestors.sms", "SMS"),
        ("ingestors.whatsapp", "WhatsApp"),
        ("ingestors.outlook", "Outlook"),
        ("ingestors.aula", "Aula"),
    ],
)

def test_forward_retries_and_logs(monkeypatch, caplog, module_name, app_name):
    mod = importlib.import_module(module_name)
    post = MagicMock(side_effect=requests.RequestException("boom"))
    monkeypatch.setattr(mod.requests, "post", post)

    with caplog.at_level(logging.WARNING):
        mod._forward({"sender": "s", "message": "m", "app": "app", "conversation_id": "1"})

    assert post.call_count == 3
    warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_logs) == 2
    error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_logs and f"Failed forwarding {app_name}" in error_logs[0].message
