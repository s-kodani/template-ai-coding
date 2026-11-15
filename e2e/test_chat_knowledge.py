"""Knowledge search e2e: Gateway MCP tools against seeded fixtures."""

from __future__ import annotations

import pytest
from conftest import (
    auth_headers,
    login_keycloak,
    reply_contains_any,
    reply_contains_seed_knowledge,
    send_chat,
)
from playwright.sync_api import Page

SEARCH_KNOWLEDGE_PROMPT = (
    "search_knowledge ツールで「Architecture Overview」を検索し、"
    "結果に含まれる技術名を1文で要約してください。"
)
GET_DOCUMENT_PROMPT = (
    "まず search_knowledge で「MCP Tools」を検索し、"
    "最初の結果の document_id を使って get_document で本文を取得し、"
    "1文で要約してください。"
)


@pytest.mark.e2e_smoke
def test_knowledge_mcp_connects_after_login(
    page: Page,
    webui_url: str,
    e2e_username: str,
    e2e_password: str,
    openai_api_key: str,
) -> None:
    del openai_api_key

    login_keycloak(page, webui_url, e2e_username, e2e_password)
    response = page.request.get(
        f"{webui_url}/api/v1/tools/id/server:mcp:knowledge/specs", headers=auth_headers(page)
    )
    assert response.ok, "Authenticated knowledge MCP discovery failed"
    assert "search_knowledge" in response.text()


def test_search_knowledge_returns_seeded_content(
    logged_in_dev: Page,
    openai_api_key: str,
) -> None:
    del openai_api_key

    reply = send_chat(logged_in_dev, SEARCH_KNOWLEDGE_PROMPT)
    assert reply_contains_seed_knowledge(reply)


def test_search_knowledge_then_get_document(
    logged_in_dev: Page,
    openai_api_key: str,
) -> None:
    del openai_api_key

    reply = send_chat(logged_in_dev, GET_DOCUMENT_PROMPT)
    assert reply_contains_any(
        reply,
        "semantic search",
        "get_document",
        "search_knowledge",
        "document chunk",
    )
