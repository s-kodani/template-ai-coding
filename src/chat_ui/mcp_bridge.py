from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from knowledge_mcp.config import Settings
from knowledge_mcp.tracing import (
    configure_langfuse_tracing,
    instrument_asyncpg,
    record_tool_output,
    tool_observation,
)

# Langfuse before FastMCP client import side effects.
_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

from fastmcp import Client


class MCPBridge:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Client | None = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        client = self._client
        if client is None:
            output = {"error": "MCP client is not configured."}
            record_tool_output(output)
            return output
        with tool_observation(name, arguments):
            async with client:
                result = await client.call_tool(name, arguments)
            if not result.content:
                output = {"error": "Tool returned no content."}
                record_tool_output(output)
                return output
            text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
            output = json.loads(text)
            record_tool_output(output)
            return output


def build_openai_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
