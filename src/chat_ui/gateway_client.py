from __future__ import annotations

from typing import Any, Protocol

import httpx
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from chat_ui.mcp_tools import catalog_from_listed_tools
from knowledge_mcp.tracing import record_tool_output, tool_observation

_TRACE_PROPAGATOR = TraceContextTextMapPropagator()
_BAGGAGE_PROPAGATOR = W3CBaggagePropagator()


class AccessTokenSource(Protocol):
    async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None: ...


class MCPGatewayClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def call_tool(
        self,
        server_id: str,
        name: str,
        arguments: dict[str, Any],
        access_token: str,
    ) -> dict[str, Any]:
        with tool_observation(name, arguments):
            headers = {"Authorization": f"Bearer {access_token}"}
            headers.update(_trace_headers())
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    f"{self._base_url}/v1/mcp/{server_id}/tools/{name}:call",
                    headers=headers,
                    json={"arguments": arguments},
                )
            if response.status_code == 401:
                output = {"error": "TOKEN_EXPIRED", "status_code": 401}
                record_tool_output(output)
                return output
            if response.status_code >= 400:
                payload = _safe_json(response)
                output = {
                    "error": payload.get("code") or f"gateway_{response.status_code}",
                    "message": payload.get("message") or "Gateway request failed",
                }
                record_tool_output(output)
                return output
            output = _safe_json(response)
            record_tool_output(output)
            return output

    async def list_servers(self, access_token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/v1/mcp",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if response.status_code >= 400:
            return []
        payload = _safe_json(response)
        servers = payload.get("servers")
        return servers if isinstance(servers, list) else []

    async def list_tools(self, server_id: str, access_token: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self._base_url}/v1/mcp/{server_id}/tools",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if response.status_code >= 400:
            return []
        payload = _safe_json(response)
        tools = payload.get("tools")
        return tools if isinstance(tools, list) else []


async def load_gateway_catalog(
    client: MCPGatewayClient,
    access_token: str,
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    listed: list[tuple[str, list[dict[str, Any]]]] = []
    for server in await client.list_servers(access_token):
        server_id = str(server.get("id") or "")
        if not server_id:
            continue
        tools = await client.list_tools(server_id, access_token)
        if tools:
            listed.append((server_id, tools))
    return catalog_from_listed_tools(listed)


async def call_gateway_tool(
    client: MCPGatewayClient,
    token_source: AccessTokenSource,
    session_id: str,
    name: str,
    arguments: dict[str, Any],
    server_id: str,
) -> dict[str, Any]:
    token = await token_source.get_access_token(session_id)
    if not token:
        return {"error": "Not authenticated for MCP tools"}
    result = await client.call_tool(server_id, name, arguments, token)
    if result.get("status_code") == 401:
        token = await token_source.get_access_token(session_id, force_refresh=True)
        if not token:
            return result
        result = await client.call_tool(server_id, name, arguments, token)
    return result


def _trace_headers() -> dict[str, str]:
    carrier: dict[str, str] = {}
    _TRACE_PROPAGATOR.inject(carrier)
    _BAGGAGE_PROPAGATOR.inject(carrier)
    return {
        key: value
        for key, value in carrier.items()
        if key.lower() in {"traceparent", "tracestate", "baggage"}
    }


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"error": response.text}
    return payload if isinstance(payload, dict) else {"result": payload}
