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


@pytest.mark.asyncio
async def test_search_knowledge_tool_validation_message() -> None:
    server = importlib.import_module("knowledge_mcp.server")

    result = await server.search_knowledge(query="", top_k=5)

    assert result["error"] == "query must not be empty"
