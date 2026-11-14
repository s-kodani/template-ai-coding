from __future__ import annotations

from typing import Any, Self

import pytest
from mcp import types
from mcp.shared.exceptions import MCPError

from mcp_gateway import mcp_client
from mcp_gateway.errors import GatewayError


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            state["client_options"] = kwargs

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def call_tool(self, name: str, arguments: dict, **kwargs: object) -> Any:
            state["request"] = {"name": name, "arguments": arguments, **kwargs}
            if state.get("error"):
                raise state["error"]
            return state["result"]

        async def list_tools(self, **kwargs: object) -> Any:
            state["request"] = kwargs
            if state.get("error"):
                raise state["error"]
            return state["result"]

        async def list_resources(self, **kwargs: object) -> Any:
            state["request"] = kwargs
            if state.get("error"):
                raise state["error"]
            return state["result"]

        async def read_resource(self, uri: str, **kwargs: object) -> Any:
            state["request"] = {"uri": uri, **kwargs}
            if state.get("error"):
                raise state["error"]
            return state["result"]

    monkeypatch.setattr(mcp_client, "Client", FakeClient)
    return state


async def test_tool_result_keeps_all_content_structured_output_and_original_error(upstream: dict) -> None:
    upstream["result"] = types.CallToolResult.model_validate({
        "content": [{"type": "text", "text": "failed"}, {"type": "text", "text": "retry"}],
        "structuredContent": {"error": "offline"},
        "isError": True,
        "_meta": {"ui": {"resourceUri": "ui://knowledge/search-results.html"}},
    })
    result = await mcp_client.call_mcp_tool(
        url="http://mcp-server:8000/mcp", token="exchanged", tool_name="search_knowledge",
        arguments={"query": "x"}, timeout_seconds=3, meta={"ui": {"page": 2}},
    )
    assert result["isError"] is True
    assert result["content"] == [{"type": "text", "text": "failed"}, {"type": "text", "text": "retry"}]
    assert result["structuredContent"] == {"error": "offline"}
    assert result["_meta"]["ui"]["resourceUri"] == "ui://knowledge/search-results.html"
    assert upstream["request"]["meta"] == {"ui": {"page": 2}}


async def test_list_tools_keeps_schema_ui_metadata_annotations_and_cursor(upstream: dict) -> None:
    upstream["result"] = types.ListToolsResult.model_validate({
        "tools": [{
            "name": "search_knowledge", "description": "Search", "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"}, "annotations": {"readOnlyHint": True},
            "_meta": {"ui": {"resourceUri": "ui://knowledge/search-results.html"}},
        }],
        "nextCursor": "next", "_meta": {"page": {"name": "first"}},
    })
    result = await mcp_client.list_mcp_tools(
        url="http://mcp-server:8000/mcp", token="exchanged", timeout_seconds=3, cursor="current",
    )
    assert result["tools"][0]["outputSchema"] == {"type": "object"}
    assert result["tools"][0]["annotations"]["readOnlyHint"] is True
    assert result["tools"][0]["_meta"]["ui"]["resourceUri"] == "ui://knowledge/search-results.html"
    assert result["nextCursor"] == "next"
    assert result["_meta"] == {"page": {"name": "first"}}
    assert upstream["request"]["cursor"] == "current"
    assert upstream["client_options"]["mode"] == "legacy"
    assert upstream["client_options"]["extensions"][0].identifier == "io.modelcontextprotocol/ui"


async def test_resource_read_keeps_html_mime_and_content_metadata(upstream: dict) -> None:
    upstream["result"] = types.ReadResourceResult.model_validate({
        "contents": [{
            "uri": "ui://knowledge/search-results.html", "mimeType": "text/html;profile=mcp-app",
            "text": "<main>Search</main>", "_meta": {"ui": {"csp": {"connectDomains": []}}},
        }],
    })
    result = await mcp_client.read_mcp_resource(
        url="http://mcp-server:8000/mcp", token="exchanged", timeout_seconds=3,
        uri="ui://knowledge/search-results.html", meta={"ui": {"view": "results"}},
    )
    assert result["contents"][0]["mimeType"] == "text/html;profile=mcp-app"
    assert result["contents"][0]["text"] == "<main>Search</main>"
    assert result["contents"][0]["_meta"] == {"ui": {"csp": {"connectDomains": []}}}
    assert upstream["request"]["meta"] == {"ui": {"view": "results"}}


async def test_resources_list_preserves_cursor_and_listing_metadata(upstream: dict) -> None:
    upstream["result"] = types.ListResourcesResult.model_validate({
        "resources": [{
            "uri": "ui://knowledge/search-results.html", "name": "Results",
            "mimeType": "text/html;profile=mcp-app", "_meta": {"ui": {"prefersBorder": True}},
        }], "nextCursor": "more",
    })
    result = await mcp_client.list_mcp_resources(
        url="http://mcp-server:8000/mcp", token="exchanged", timeout_seconds=3, cursor="second",
    )
    assert result["resources"][0]["_meta"] == {"ui": {"prefersBorder": True}}
    assert result["nextCursor"] == "more"
    assert upstream["request"]["cursor"] == "second"


@pytest.mark.parametrize("operation", ["tool", "tools", "resources", "resource"])
@pytest.mark.parametrize("timeout", [TimeoutError("private details"), MCPError(types.REQUEST_TIMEOUT, "private details")])
async def test_upstream_timeout_maps_to_gateway_timeout(
    upstream: dict, operation: str, timeout: Exception,
) -> None:
    upstream["error"] = timeout
    kwargs = {"url": "http://mcp-server:8000/mcp", "token": "exchanged", "timeout_seconds": 3}
    with pytest.raises(GatewayError) as exc:
        if operation == "tool":
            await mcp_client.call_mcp_tool(**kwargs, tool_name="search_knowledge", arguments={})
        elif operation == "tools":
            await mcp_client.list_mcp_tools(**kwargs)
        elif operation == "resources":
            await mcp_client.list_mcp_resources(**kwargs)
        else:
            await mcp_client.read_mcp_resource(**kwargs, uri="ui://knowledge/search-results.html")
    assert exc.value.status_code == 504
    assert exc.value.code == "MCP_TIMEOUT"
    assert "private details" not in exc.value.message
