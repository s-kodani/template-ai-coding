"""The Open WebUI MCP catalog follows the logged-in user's Keycloak roles."""

from __future__ import annotations

from conftest import auth_headers, tools_catalog
from playwright.sync_api import Page

KNOWLEDGE = "server:mcp:knowledge"
WEB_SEARCH = "server:mcp:web-search"


def tool_specs(page: Page, webui_url: str, server_id: str):
    """Discover through the authenticated host, including Gateway Token Exchange."""
    return page.request.get(
        f"{webui_url}/api/v1/tools/id/{server_id}/specs",
        headers=auth_headers(page),
    )


def test_dev2_catalog_only_contains_web_search(logged_in_dev2: Page, webui_url: str) -> None:
    ids = {tool["id"] for tool in tools_catalog(logged_in_dev2, webui_url)}
    assert ids == {WEB_SEARCH}


def test_dev2_can_discover_web_search_tools(logged_in_dev2: Page, webui_url: str) -> None:
    response = tool_specs(logged_in_dev2, webui_url, WEB_SEARCH)
    assert response.status == 200
    assert {tool["name"] for tool in response.json()["specs"]} == {"search_web"}
