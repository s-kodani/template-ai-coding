from __future__ import annotations

import os

from web_search_mcp.tracing import configure_langfuse_tracing, record_tool_input, record_tool_output

# Langfuse must initialize before FastMCP import.
_langfuse = configure_langfuse_tracing()

from fastmcp import FastMCP

from web_search_mcp.auth import build_mcp_auth, require_web_search_reader
from web_search_mcp.config import get_settings
from web_search_mcp.search_client import BraveSearchClient

settings = get_settings()
search_client = BraveSearchClient(
    api_key=settings.brave_search_api_key,
    base_url=settings.brave_search_base_url,
    timeout=settings.search_timeout,
)

mcp = FastMCP(
    name="web-search-mcp",
    instructions="Search the public web with Brave Search and return concise result snippets.",
    auth=build_mcp_auth(settings),
)


@mcp.tool(auth=require_web_search_reader)
async def search_web(query: str, count: int = 5) -> dict:
    """Search the public web for pages matching the query."""
    record_tool_input({"query": query, "count": count})
    try:
        result = await search_client.search_web(query=query, count=count)
    except ValueError as exc:
        output = {"error": str(exc)}
        record_tool_output(output)
        return output
    except Exception as exc:  # noqa: BLE001 - return LLM-actionable errors
        output = {"error": str(exc)}
        record_tool_output(output)
        return output
    output = result.model_dump()
    record_tool_output(output)
    return output


def main() -> None:
    os.environ.setdefault("FASTMCP_STATELESS_HTTP", "true")
    os.environ.setdefault("FASTMCP_TELEMETRY_MODE", "native")
    mcp.run(
        transport="http",
        host=settings.mcp_host,
        port=settings.mcp_port,
        path=settings.mcp_path,
    )


if __name__ == "__main__":
    main()
