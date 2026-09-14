"""Authentication gate: chat requires Keycloak login."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_unauthenticated_user_cannot_chat(page: Page, chainlit_url: str) -> None:
    page.goto(chainlit_url, wait_until="domcontentloaded")
    expect(page.locator("#chat-input")).not_to_be_visible(timeout=10_000)
