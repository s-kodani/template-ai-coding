"""ReauthRequired e2e: cleared token store blocks MCP connect until re-login."""

from __future__ import annotations

import pytest
from conftest import (
    REAUTH_REQUIRED_DETAIL,
    clear_oauth_tokens,
    expect_mcp_post,
    login_keycloak,
    logout_chainlit,
    mcp_api_request,
    mcp_disconnect,
)
from playwright.sync_api import Page

pytestmark = pytest.mark.e2e_reauth


def test_mcp_connect_requires_relogin_after_token_cleared(
    page: Page,
    chainlit_url: str,
    chainlit_session_id: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    mcp_disconnect(page, chainlit_url, chainlit_session_id, "knowledge-mcp")
    clear_oauth_tokens(chainlit_session_id)

    blocked = mcp_api_request(
        page,
        chainlit_url,
        "POST",
        chainlit_session_id,
        "knowledge-mcp",
    )
    assert blocked.status == 403
    assert REAUTH_REQUIRED_DETAIL in blocked.text()

    logout_chainlit(page, chainlit_url)
    with expect_mcp_post(page, server_name="knowledge-mcp") as response_info:
        login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    assert response_info.value.status == 200
