"""Admin-registered MCPs remain usable across host discovery and page reloads."""

from __future__ import annotations

from conftest import tools_catalog
from playwright.sync_api import Page, expect
from test_mcp_catalog_ui import KNOWLEDGE, WEB_SEARCH, tool_specs


def test_dev_discovers_both_gateway_mcps(logged_in_dev: Page, webui_url: str) -> None:
    assert {tool["id"] for tool in tools_catalog(logged_in_dev, webui_url)} == {
        KNOWLEDGE, WEB_SEARCH,
    }
    knowledge = tool_specs(logged_in_dev, webui_url, KNOWLEDGE)
    assert knowledge.status == 200
    assert {tool["name"] for tool in knowledge.json()["specs"]} == {
        "search_knowledge", "get_document",
    }
    web_search = tool_specs(logged_in_dev, webui_url, WEB_SEARCH)
    assert web_search.status == 200
    assert {tool["name"] for tool in web_search.json()["specs"]} == {"search_web"}


def test_reload_keeps_authenticated_gateway_discovery(logged_in_dev: Page, webui_url: str) -> None:
    before = tool_specs(logged_in_dev, webui_url, KNOWLEDGE)
    assert before.status == 200

    logged_in_dev.reload(wait_until="domcontentloaded")
    expect(logged_in_dev.locator("#chat-input")).to_be_visible(timeout=60_000)

    after = tool_specs(logged_in_dev, webui_url, KNOWLEDGE)
    assert after.status == 200
    assert {tool["name"] for tool in after.json()["specs"]} == {
        "search_knowledge", "get_document",
    }
