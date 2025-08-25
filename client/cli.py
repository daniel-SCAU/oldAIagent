import argparse
import os
from typing import List

import requests

DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_API_KEY = os.getenv("API_KEY", "")


def _headers(api_key: str) -> dict:
    return {"X-API-KEY": api_key} if api_key else {}


def _get(base_url: str, api_key: str, path: str):
    resp = requests.get(f"{base_url}{path}", headers=_headers(api_key))
    resp.raise_for_status()
    return resp.json()


def _post(base_url: str, api_key: str, path: str, payload: dict):
    resp = requests.post(
        f"{base_url}{path}", json=payload, headers=_headers(api_key)
    )
    resp.raise_for_status()
    return resp.json()


def list_conversations(base_url: str, api_key: str) -> List[str]:
    tasks = _get(base_url, api_key, "/tasks")
    ids = sorted({t["conversation_id"] for t in tasks})
    return ids


def get_summary(conversation_id: str, base_url: str, api_key: str) -> str:
    tasks = _get(base_url, api_key, "/tasks")
    for t in tasks:
        if t["conversation_id"] == conversation_id and t.get("summary"):
            return t["summary"]
    return ""


def list_tasks(base_url: str, api_key: str):
    return _get(base_url, api_key, "/tasks")


def request_suggestions(
    conversation_id: str, base_url: str, api_key: str, limit: int = 3
) -> List[str]:
    data = _post(
        base_url, api_key, "/suggestions", {"conversation_id": conversation_id, "limit": limit}
    )
    return data.get("suggestions", [])


def main():
    parser = argparse.ArgumentParser(description="myGPT API client")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)

    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("conversations", help="List conversation IDs")

    sp_sum = sub.add_parser("summary", help="Show summary for a conversation")
    sp_sum.add_argument("conversation_id")

    sub.add_parser("tasks", help="List tasks")

    sp_sug = sub.add_parser("suggest", help="Request reply suggestions")
    sp_sug.add_argument("conversation_id")
    sp_sug.add_argument("--limit", type=int, default=3)

    args = parser.parse_args()
    base_url = args.base_url
    api_key = args.api_key

    if args.cmd == "conversations":
        for cid in list_conversations(base_url, api_key):
            print(cid)
    elif args.cmd == "summary":
        summary = get_summary(args.conversation_id, base_url, api_key)
        print(summary or "No summary available")
    elif args.cmd == "tasks":
        for t in list_tasks(base_url, api_key):
            print(f"{t['id']} {t['conversation_id']} {t['status']}")
    elif args.cmd == "suggest":
        for s in request_suggestions(args.conversation_id, base_url, api_key, args.limit):
            print(f"- {s}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
