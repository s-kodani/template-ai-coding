"""Authentication gate: chat requires Keycloak login."""

from __future__ import annotations

import pytest
from conftest import goto_webui, login_keycloak, logout_webui, send_chat
from playwright.sync_api import Page, expect


@pytest.mark.e2e_smoke
def test_unauthenticated_user_cannot_chat(page: Page, webui_url: str) -> None:
    goto_webui(page, webui_url)
    expect(page.locator("#chat-input")).not_to_be_visible(timeout=10_000)


def test_logout_then_login_restores_chat(
    page: Page,
    webui_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(page, webui_url, e2e_username, e2e_password)
    logout_webui(page, webui_url)
    goto_webui(page, webui_url)
    expect(page.locator("#chat-input")).not_to_be_visible(timeout=10_000)

    login_keycloak(page, webui_url, e2e_username, e2e_password)
    reply = send_chat(page, "こんにちはとだけ答えてください。ツールは不要です。")
    assert reply.inner_text().strip()
