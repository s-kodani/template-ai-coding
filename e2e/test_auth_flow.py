"""Authentication gate: chat requires Keycloak login."""

from __future__ import annotations

from conftest import login_keycloak, logout_chainlit, send_chat
from playwright.sync_api import Page, expect


def test_unauthenticated_user_cannot_chat(page: Page, chainlit_url: str) -> None:
    page.goto(chainlit_url, wait_until="domcontentloaded")
    expect(page.locator("#chat-input")).not_to_be_visible(timeout=10_000)


def test_logout_then_login_restores_chat(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    logout_chainlit(page, chainlit_url)
    page.goto(chainlit_url, wait_until="domcontentloaded")
    expect(page.locator("#chat-input")).not_to_be_visible(timeout=10_000)

    login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    reply = send_chat(page, "こんにちはとだけ答えてください。ツールは不要です。")
    assert reply.inner_text().strip()
