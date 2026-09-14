"""Gateway MCP lifecycle: dual connect, disconnect, and reconnect."""

from __future__ import annotations

from conftest import (
    capture_session_id_from_response,
    expect_mcp_post,
    login_keycloak,
    mcp_connect,
    mcp_disconnect,
    reply_contains_seed_knowledge,
    send_chat,
)
from playwright.sync_api import Page

KNOWLEDGE_PROMPT = (
    "search_knowledge ツールで「Architecture Overview」を検索し、"
    "結果に含まれる技術名を1文で要約してください。"
)


def test_dev_connects_both_gateway_mcps(
    page: Page,
    chainlit_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    with expect_mcp_post(page, server_name="knowledge-mcp") as knowledge_response:
        login_keycloak(page, chainlit_url, e2e_username, e2e_password)
    assert knowledge_response.value.status == 200
    session_id = capture_session_id_from_response(knowledge_response.value)

    web_search_response = mcp_connect(
        page,
        chainlit_url,
        session_id,
        "web-search-mcp",
    )
    assert web_search_response.status == 200


def test_disconnect_blocks_knowledge_until_reconnect(
    page: Page,
    chainlit_url: str,
    chainlit_session_id: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    mcp_disconnect(page, chainlit_url, chainlit_session_id, "knowledge-mcp")

    blocked = send_chat(page, KNOWLEDGE_PROMPT)
    assert not reply_contains_seed_knowledge(blocked)

    response = mcp_connect(
        page,
        chainlit_url,
        chainlit_session_id,
        "knowledge-mcp",
    )
    payload = response.json()
    tools = payload["mcp"]["tools"]
    tool_names = {str(tool["name"]) for tool in tools}
    assert payload["mcp"]["status"] == "connected"
    assert "search_knowledge" in tool_names
