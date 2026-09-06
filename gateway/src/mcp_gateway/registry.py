from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mcp_gateway.errors import GatewayError


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def _servers_for_process(data: dict[str, Any], public_base_url: str | None) -> Any:
    gateways = data.get("gateways")
    if isinstance(gateways, list) and gateways:
        matched: dict[str, Any] | None = None
        if public_base_url:
            want = _normalize_url(public_base_url)
            for gateway in gateways:
                if not isinstance(gateway, dict):
                    continue
                if _normalize_url(str(gateway.get("url") or "")) == want:
                    matched = gateway
                    break
        if matched is None and len(gateways) == 1 and isinstance(gateways[0], dict):
            matched = gateways[0]
        if matched is None:
            return {}
        return matched.get("servers") or {}
    return data.get("servers") or {}


def load_registry(path: str | Path, *, public_base_url: str | None = None) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    servers = _servers_for_process(data, public_base_url)
    if not isinstance(servers, dict):
        raise TypeError("registry servers must be a mapping")
    return servers


def get_server(registry: dict[str, Any], server_id: str) -> dict[str, Any]:
    server = registry.get(server_id)
    if not server or not server.get("enabled", True):
        raise GatewayError(404, "MCP_SERVER_NOT_FOUND", "MCP server is not registered")
    return server


def list_enabled_servers(
    registry: dict[str, Any],
    roles: frozenset[str] | set[str] | None = None,
    *,
    public_base_url: str = "http://mcp-gateway:8082",
) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    caller_roles = set(roles or [])
    base = public_base_url.rstrip("/")
    for server_id, server in registry.items():
        if not isinstance(server, dict) or not server.get("enabled", True):
            continue
        required = set((server.get("authorization") or {}).get("required_roles") or [])
        if required and not required.issubset(caller_roles):
            continue
        ui = server.get("ui") or {}
        allowed = list((server.get("authorization") or {}).get("allowed_tools") or [])
        listed.append(
            {
                "id": server_id,
                "name": ui.get("name") or server_id,
                "tools": allowed,
                "url": f"{base}/mcp/{server_id}",
            }
        )
    return listed
