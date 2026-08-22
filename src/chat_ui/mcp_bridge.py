from __future__ import annotations

import json
from typing import Any

from fastmcp import Client
from openai import AsyncOpenAI

from knowledge_mcp.config import Settings
from knowledge_mcp.tracing import configure_langfuse_tracing, instrument_asyncpg, tool_observation

# Langfuse before FastMCP client import side effects.
_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "Search the local knowledge base for relevant passages.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    },
}

GET_DOCUMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "get_document",
        "description": "Fetch a full document by id from search results.",
        "parameters": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
}


class MCPBridge:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = Client(settings.mcp_server_url)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with tool_observation(name, arguments):
            async with self._client:
                result = await self._client.call_tool(name, arguments)
            if not result.content:
                return {"error": "Tool returned no content."}
            text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
            return json.loads(text)


def build_openai_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
