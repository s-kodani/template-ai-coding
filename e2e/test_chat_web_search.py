"""Web search e2e: dev2 uses search_web via Gateway MCP."""

from __future__ import annotations

import pytest
from conftest import reply_contains_any, reply_contains_url, send_chat
from playwright.sync_api import Page

pytestmark = pytest.mark.e2e_brave

SEARCH_WEB_PROMPT = (
    "search_web ツールで「pytest documentation」を検索し、"
    "見つかった公式ドキュメントの URL を1つだけ答えてください。"
)


def test_dev2_search_web_returns_url(
    logged_in_dev2: Page,
    openai_api_key: str,
    brave_search_api_key: str,
) -> None:
    del openai_api_key, brave_search_api_key

    reply = send_chat(logged_in_dev2, SEARCH_WEB_PROMPT)
    assert reply_contains_url(reply)


def test_search_web_without_api_key_reports_error(
    logged_in_dev2: Page,
    openai_api_key: str,
    require_empty_brave_search_api_key: None,
) -> None:
    del openai_api_key, require_empty_brave_search_api_key

    reply = send_chat(logged_in_dev2, SEARCH_WEB_PROMPT)
    assert reply_contains_any(
        reply,
        "API key",
        "BRAVE_SEARCH_API_KEY",
        "error",
        "利用",
    )
