from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import httpx

from chat_ui.mcp_tools import catalog_from_listed_tools, parse_tool_result
from knowledge_mcp.tracing import (
    inject_langfuse_propagated_meta,
    record_tool_output,
    tool_observation,
)

McpClientFactory = Callable[[str, str], Any]


class AccessTokenSource(Protocol):
    async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None: ...


def _default_mcp_client(url: str, token: str) -> Any:
    from fastmcp import Client

    return Client(url, auth=token)


class MCPGatewayClient:
    def __init__(
        self,
        base_url: str,
        mcp_client_factory: McpClientFactory | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._mcp_client_factory = mcp_client_factory or _default_mcp_client

    def _mcp_url(self, server_id: str, url: str | None) -> str:
        if url:
            return url.rstrip("/")
        return f"{self._base_url}/mcp/{server_id}"

    async def call_tool(
        self,
        server_id: str,
        name: str,
        arguments: dict[str, Any],
        access_token: str,
        url: str | None = None,
        *,
        tool_metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with tool_observation(name, arguments, metadata=tool_metadata):
            try:
                async with self._mcp_client_factory(
                    self._mcp_url(server_id, url), access_token
                ) as client:
                    result = await client.call_tool(
                        name, arguments, meta=inject_langfuse_propagated_meta({})
                    )
            except Exception as exc:  # noqa: BLE001 - map FastMCP/httpx failures to tool output
                output = _mcp_error(exc)
                record_tool_output(output)
                return output
            output = parse_tool_result(result)
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

    async def list_tools(
        self,
        server_id: str,
        access_token: str,
        url: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            async with self._mcp_client_factory(
                self._mcp_url(server_id, url), access_token
            ) as client:
                listed = await client.list_tools()
        except Exception:  # noqa: BLE001 - missing schema must not block other servers
            return []
        tools = getattr(listed, "tools", listed) or []
        mapped: list[dict[str, Any]] = []
        for tool in tools:
            mapped.append(
                {
                    "name": tool.name,
                    "description": getattr(tool, "description", "") or "",
                    "inputSchema": getattr(tool, "inputSchema", None)
                    or getattr(tool, "input_schema", None)
                    or {},
                }
            )
        return mapped


async def resolve_gateway_url(
    client: MCPGatewayClient,
    server_id: str,
    access_token: str,
) -> str | None:
    for server in await client.list_servers(access_token):
        if str(server.get("id") or "") == server_id:
            url = str(server.get("url") or "").strip()
            return url or None
    return None


async def load_gateway_catalog(
    client: MCPGatewayClient,
    access_token: str,
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    listed: list[tuple[str, list[dict[str, Any]]]] = []
    for server in await client.list_servers(access_token):
        server_id = str(server.get("id") or "")
        if not server_id:
            continue
        url = str(server.get("url") or "") or None
        tools = await client.list_tools(server_id, access_token, url=url)
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
    *,
    tool_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    token = await token_source.get_access_token(session_id)
    if not token:
        return {"error": "Not authenticated for MCP tools"}
    result = await client.call_tool(
        server_id, name, arguments, token, tool_metadata=tool_metadata
    )
    if result.get("status_code") == 401:
        token = await token_source.get_access_token(session_id, force_refresh=True)
        if not token:
            return result
        result = await client.call_tool(
            server_id, name, arguments, token, tool_metadata=tool_metadata
        )
    return result


def _mcp_error(exc: BaseException) -> dict[str, Any]:
    status = _http_status(exc)
    if status == 401:
        return {"error": "TOKEN_EXPIRED", "status_code": 401}
    if status is not None:
        return {"error": f"gateway_{status}", "message": str(exc) or "Gateway request failed"}
    return {"error": "MCP_UPSTREAM_ERROR", "message": str(exc) or "Gateway request failed"}


def _http_status(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) if response is not None else None
    if isinstance(status, int):
        return status
    cause = exc.__cause__ or exc.__context__
    if cause is not None and cause is not exc:
        return _http_status(cause)
    return None


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {"error": response.text}
    return payload if isinstance(payload, dict) else {"result": payload}
