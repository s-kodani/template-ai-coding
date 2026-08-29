from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from mcp_gateway.errors import GatewayError


def load_registry(path: str | Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    servers = data.get("servers") or {}
    if not isinstance(servers, dict):
        raise TypeError("registry servers must be a mapping")
    return servers


def get_server(registry: dict[str, Any], server_id: str) -> dict[str, Any]:
    server = registry.get(server_id)
    if not server or not server.get("enabled", True):
        raise GatewayError(404, "MCP_SERVER_NOT_FOUND", "MCP server is not registered")
    return server
