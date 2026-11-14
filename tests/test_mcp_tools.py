import importlib

import pytest


@pytest.mark.asyncio
async def test_search_knowledge_tool_schema() -> None:
    server = importlib.import_module("knowledge_mcp.server")

    tools = await server.mcp.list_tools()
    by_name = {tool.name: tool for tool in tools}

    assert "search_knowledge" in by_name
    assert "get_document" in by_name

    search = by_name["search_knowledge"]
    assert search.description
    assert "query" in search.parameters["properties"]
    assert "top_k" in search.parameters["properties"]

    get_document = by_name["get_document"]
    assert "chunk" in get_document.description.lower()
    assert "full document" not in get_document.description.lower()


@pytest.mark.asyncio
async def test_search_knowledge_tool_validation_message() -> None:
    server = importlib.import_module("knowledge_mcp.server")

    result = await server.search_knowledge(query="", top_k=5)

    assert result["error"] == "query must not be empty"


@pytest.mark.asyncio
async def test_search_tool_declares_app_and_pagination_schema() -> None:
    from unittest.mock import AsyncMock, patch

    from fastmcp import Client

    server = importlib.import_module("knowledge_mcp.server")
    with (
        patch.object(server.repository, "connect", AsyncMock()),
        patch.object(server.repository, "close", AsyncMock()),
        patch.object(server.embedding_client, "aclose", AsyncMock()),
    ):
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            search = tools["search_knowledge"]
            assert search.meta["ui"]["resourceUri"] == "ui://knowledge/search-results.html"
            assert search.inputSchema["properties"]["offset"]["default"] == 0
            resources = await client.list_resources()
            resource = next(r for r in resources if str(r.uri) == "ui://knowledge/search-results.html")
            assert resource.mimeType == "text/html;profile=mcp-app"
            content = await client.read_resource("ui://knowledge/search-results.html")

    assert content[0].mimeType == "text/html;profile=mcp-app"
    assert "ナレッジ検索" in content[0].text
    assert "<script" in content[0].text
    assert content[0].meta["ui"]["csp"]["connectDomains"] == []
