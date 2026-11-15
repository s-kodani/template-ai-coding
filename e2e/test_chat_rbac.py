"""Role denial is enforced by the host as well as the MCP Gateway."""

from __future__ import annotations

from conftest import login_keycloak, tools_catalog
from playwright.sync_api import Page
from test_mcp_catalog_ui import KNOWLEDGE, WEB_SEARCH, tool_specs


def test_dev2_cannot_use_knowledge_connection(logged_in_dev2: Page, webui_url: str) -> None:
    assert tool_specs(logged_in_dev2, webui_url, KNOWLEDGE).status == 404


def test_readerless_cannot_use_either_mcp(
    page: Page,
    webui_url: str,
    e2e_readerless_username: str,
    e2e_readerless_password: str,
) -> None:
    login_keycloak(page, webui_url, e2e_readerless_username, e2e_readerless_password)
    assert tools_catalog(page, webui_url) == []
    assert tool_specs(page, webui_url, KNOWLEDGE).status == 404
    assert tool_specs(page, webui_url, WEB_SEARCH).status == 404
