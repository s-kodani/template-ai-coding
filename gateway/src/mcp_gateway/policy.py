from __future__ import annotations

from typing import Any

from mcp_gateway.errors import GatewayError
from mcp_gateway.principal import Principal


def authorize_server(principal: Principal, server: dict[str, Any]) -> None:
    required_roles = set(server.get("authorization", {}).get("required_roles") or [])
    if required_roles and not required_roles.issubset(principal.roles):
        raise GatewayError(403, "ACCESS_DENIED", "User is not permitted to access this MCP server")


def authorize_tool(principal: Principal, server: dict[str, Any], tool_name: str) -> None:
    allowed = list(server.get("authorization", {}).get("allowed_tools") or [])
    if tool_name not in allowed:
        raise GatewayError(404, "TOOL_NOT_FOUND", "Tool is not allowed")
    authorize_server(principal, server)


def authorize_resource(principal: Principal, server: dict[str, Any], uri: str) -> None:
    authorize_server(principal, server)
    allowed = list(server.get("authorization", {}).get("allowed_resources") or [])
    if uri not in allowed:
        raise GatewayError(404, "RESOURCE_NOT_FOUND", "Resource is not allowed")
