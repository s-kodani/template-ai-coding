"""Chainlit smoke: Keycloak login then one chat turn."""

from __future__ import annotations

from conftest import login_keycloak, send_chat
from playwright.sync_api import Page

PROMPT = (
    "search_knowledge を使って Architecture Overview と MCP Tools を調べ、"
    "1文で要約してください。"
)


def test_keycloak_login_then_one_chat_turn(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    reply = send_chat(page, PROMPT)
    assert reply.inner_text().strip()
