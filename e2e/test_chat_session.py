"""Multi-turn chat session without MCP tools."""

from __future__ import annotations

from conftest import login_keycloak, reply_contains_any, send_chat
from playwright.sync_api import Page

SESSION_NAME = "E2E-W2"
TURN_ONE = f"私の名前は{SESSION_NAME}です。覚えてください。ツールは使わないで。"
TURN_TWO = "私の名前を答えてください。ツールは不要です。"


def test_multi_turn_remembers_session_context(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    send_chat(page, TURN_ONE)
    reply = send_chat(page, TURN_TWO)
    assert reply_contains_any(reply, SESSION_NAME)
