"""Native Open WebUI multi-turn conversation context."""

from __future__ import annotations

from conftest import reply_contains_any, send_chat
from playwright.sync_api import Page

SESSION_NAME = "E2E-W2"
TURN_ONE = f"私の名前は{SESSION_NAME}です。覚えてください。ツールは使わないで。"
TURN_TWO = "私の名前を答えてください。ツールは不要です。"


def test_multi_turn_remembers_session_context(
    logged_in_dev: Page,
    openai_api_key: str,
) -> None:
    del openai_api_key

    send_chat(logged_in_dev, TURN_ONE)
    reply = send_chat(logged_in_dev, TURN_TWO)
    assert reply_contains_any(reply, SESSION_NAME)
