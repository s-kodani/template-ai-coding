"""Chainlit smoke: Keycloak login then one chat turn."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

CHAT_TIMEOUT_MS = 120_000
PROMPT = (
    "search_knowledge を使って Architecture Overview と MCP Tools を調べ、"
    "1文で要約してください。"
)
_PROVIDER_BUTTON = re.compile(r"keycloak", re.IGNORECASE)


def test_keycloak_login_then_one_chat_turn(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    page.goto(f"{chainlit_url}/login", wait_until="domcontentloaded")
    page.get_by_role("button", name=_PROVIDER_BUTTON).click()
    page.locator("#username").fill(e2e_username)
    page.locator("#password").fill(e2e_password)
    page.locator("#kc-login").click()

    chat_input = page.locator("#chat-input")
    expect(chat_input).to_be_visible(timeout=60_000)
    chat_input.fill(PROMPT)
    page.locator("#chat-submit").click()

    reply = page.locator('[data-step-type="assistant_message"]').last
    expect(reply).to_be_visible(timeout=CHAT_TIMEOUT_MS)
    assert reply.inner_text().strip()
