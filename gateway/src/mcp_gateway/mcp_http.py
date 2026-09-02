from __future__ import annotations

import json
from typing import Any

from fastapi.responses import JSONResponse, Response

from mcp_gateway.errors import GatewayError
from mcp_gateway.mcp_client import _trace_meta
from mcp_gateway.policy import authorize_tool


def jsonrpc_result(rpc_id: object, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": rpc_id, "result": result},
        media_type="application/json",
    )


def initialize_result(params: dict[str, Any] | None) -> dict[str, Any]:
    version = "2025-11-25"
    if isinstance(params, dict) and params.get("protocolVersion"):
        version = str(params["protocolVersion"])
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {"name": "mcp-gateway", "version": "0.1.0"},
    }


def forwarded_meta(params: dict[str, Any] | None) -> dict[str, str] | None:
    incoming: dict[str, str] = {}
    if isinstance(params, dict):
        meta = params.get("_meta")
        if isinstance(meta, dict):
            incoming = {str(key): str(value) for key, value in meta.items()}
    merged = {**_trace_meta(), **incoming}
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
    timeout_seconds: float,
) -> JSONResponse | Response:
    if method == "initialize":
        return jsonrpc_result(rpc_id, initialize_result(params))
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return Response(status_code=202)
    if method == "ping":
        return jsonrpc_result(rpc_id, {})
    if method == "tools/list":
        tools = await lister(
            url=server["transport"]["url"],
            token=mcp_token,
            timeout_seconds=timeout_seconds,
        )
        allowed = set(server.get("authorization", {}).get("allowed_tools") or [])
        return jsonrpc_result(
            rpc_id,
            {"tools": [tool for tool in tools if tool.get("name") in allowed]},
        )
    if method == "tools/call":
        payload = params or {}
        tool_name = str(payload.get("name") or "")
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        authorize_tool(principal, server, tool_name)
        output = await caller(
            url=server["transport"]["url"],
            token=mcp_token,
            tool_name=tool_name,
            arguments=arguments,
            timeout_seconds=timeout_seconds,
            meta=forwarded_meta(payload),
        )
        return jsonrpc_result(
            rpc_id,
            {"content": [{"type": "text", "text": json.dumps(output)}], "isError": False},
        )
    raise GatewayError(400, "METHOD_NOT_FOUND", f"Unsupported MCP method: {method}")
