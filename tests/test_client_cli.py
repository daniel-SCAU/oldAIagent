import sys
from unittest.mock import Mock, patch
from pathlib import Path

# Ensure the project root is on the import path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from client import cli


def _mock_response(data):
    resp = Mock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_list_conversations():
    data = [
        {"conversation_id": "1", "id": 1, "status": "completed", "summary": "Hi"},
        {"conversation_id": "2", "id": 2, "status": "pending", "summary": None},
        {"conversation_id": "1", "id": 3, "status": "completed", "summary": "Bye"},
    ]
    with patch("client.cli.requests.get", return_value=_mock_response(data)) as mock_get:
        ids = cli.list_conversations("http://example", "key")
        assert ids == ["1", "2"]
        mock_get.assert_called_once()


def test_request_suggestions():
    payload = {"suggestions": ["Hello", "How are you?"]}
    with patch("client.cli.requests.post", return_value=_mock_response(payload)) as mock_post:
        suggestions = cli.request_suggestions("1", "http://example", "key", limit=2)
        assert suggestions == ["Hello", "How are you?"]
        mock_post.assert_called_once()
