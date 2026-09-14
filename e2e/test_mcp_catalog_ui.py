"""MCP catalog and reconnect behavior in the browser."""

from __future__ import annotations

from conftest import (
    expect_mcp_post,
    mcp_api_request,
    mcp_connect,
    mcp_disconnect,
    reply_contains_seed_knowledge,
    send_chat,
)
from playwright.sync_api import Page, expect

KNOWLEDGE_PROMPT = (
    "search_knowledge ツールで「Architecture Overview」を検索し、"
    "結果に含まれる技術名を1文で要約してください。"
)


def test_dev2_cannot_connect_knowledge_mcp(
    page: Page,
    chainlit_url: str,
    chainlit_session_id_dev2: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    response = mcp_api_request(
        page,
        chainlit_url,
        "POST",
        chainlit_session_id_dev2,
        "knowledge-mcp",
    )
    assert response.status == 403


def test_dev2_can_connect_web_search_mcp(
    page: Page,
    chainlit_url: str,
    chainlit_session_id_dev2: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    response = mcp_connect(
        page,
        chainlit_url,
        chainlit_session_id_dev2,
        "web-search-mcp",
    )
    assert response.status == 200


def test_reload_reconnects_gateway_mcp_after_disconnect(
    page: Page,
    chainlit_url: str,
    chainlit_session_id: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    mcp_disconnect(page, chainlit_url, chainlit_session_id, "knowledge-mcp")

    with expect_mcp_post(page, server_name="knowledge-mcp") as response_info:
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#chat-input")).to_be_visible(timeout=60_000)
    assert response_info.value.status == 200

    reply = send_chat(page, KNOWLEDGE_PROMPT)
    assert reply_contains_seed_knowledge(reply)
