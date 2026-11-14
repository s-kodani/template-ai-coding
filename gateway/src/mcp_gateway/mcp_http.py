from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse, Response

from mcp_gateway.errors import GatewayError
from mcp_gateway.mcp_client import _trace_meta
from mcp_gateway.policy import authorize_resource, authorize_server, authorize_tool


def jsonrpc_result(rpc_id: object, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": rpc_id, "result": result},
        media_type="application/json",
    )


def initialize_result(_params: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "protocolVersion": "2025-11-25",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"listChanged": False, "subscribe": False},
            "extensions": {"io.modelcontextprotocol/ui": {}},
        },
        "serverInfo": {"name": "mcp-gateway", "version": "0.1.0"},
    }


def forwarded_meta(params: dict[str, Any] | None) -> dict[str, Any] | None:
    incoming = params.get("_meta") if isinstance(params, dict) else None
    merged = {**_trace_meta(), **(incoming if isinstance(incoming, dict) else {})}
    return merged or None


async def dispatch_mcp_method(
    *,
    method: str,
    params: dict[str, Any] | None,
    rpc_id: object,
    principal: Any,
    server: dict[str, Any],
    mcp_token: str | None,
    lister: Any,
    caller: Any,
    resource_lister: Any,
    resource_reader: Any,
    timeout_seconds: float,
) -> JSONResponse | Response:
    if method == "initialize":
        return jsonrpc_result(rpc_id, initialize_result(params))
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return Response(status_code=202)
    if method == "ping":
        return jsonrpc_result(rpc_id, {})
    payload = params or {}
    upstream = {
        "url": server["transport"]["url"],
        "token": mcp_token,
        "timeout_seconds": timeout_seconds,
        "meta": forwarded_meta(payload),
    }
    if method == "tools/list":
        authorize_server(principal, server)
        page = await lister(**upstream, cursor=payload.get("cursor"))
        allowed = set(server.get("authorization", {}).get("allowed_tools") or [])
        return jsonrpc_result(
            rpc_id,
            {**page, "tools": [tool for tool in page["tools"] if tool.get("name") in allowed]},
        )
    if method == "tools/call":
        tool_name = str(payload.get("name") or "")
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        authorize_tool(principal, server, tool_name)
        output = await caller(**upstream, tool_name=tool_name, arguments=arguments)
        return jsonrpc_result(rpc_id, output)
    if method == "resources/list":
        authorize_server(principal, server)
        allowed = set(server.get("authorization", {}).get("allowed_resources") or [])
        if not allowed:
            return jsonrpc_result(rpc_id, {"resources": []})
        page = await resource_lister(**upstream, cursor=payload.get("cursor"))
        return jsonrpc_result(rpc_id, {
            **page,
            "resources": [resource for resource in page["resources"] if resource.get("uri") in allowed],
        })
    if method == "resources/read":
        uri = str(payload.get("uri") or "")
        authorize_resource(principal, server, uri)
        return jsonrpc_result(rpc_id, await resource_reader(**upstream, uri=uri))
    raise GatewayError(400, "METHOD_NOT_FOUND", f"Unsupported MCP method: {method}")
