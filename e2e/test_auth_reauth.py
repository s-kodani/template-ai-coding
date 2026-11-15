"""An invalid UI session is rejected; a fresh Keycloak login restores access."""

from __future__ import annotations

import pytest
from conftest import auth_headers, goto_webui, login_keycloak, tools_catalog
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e_reauth


def test_invalid_webui_token_requires_login_and_restores_mcp_catalog(
    logged_in_dev: Page,
    webui_url: str,
    e2e_username: str,
    e2e_password: str,
) -> None:
    page = logged_in_dev
    assert any(item["id"] == "server:mcp:knowledge" for item in tools_catalog(page, webui_url))

    # A rejected UI credential cannot fall back to a browser cookie.
    page.evaluate('() => localStorage.setItem("token", "invalid-session-token")')
    page.context.clear_cookies()
    blocked = page.request.get(f"{webui_url}/api/v1/tools/", headers=auth_headers(page))
    assert blocked.status == 401
    page.evaluate('() => localStorage.removeItem("token")')
    goto_webui(page, f"{webui_url}/auth")
    expect(page.locator("#chat-input")).not_to_be_visible()

    login_keycloak(page, webui_url, e2e_username, e2e_password)
    assert any(item["id"] == "server:mcp:knowledge" for item in tools_catalog(page, webui_url))
