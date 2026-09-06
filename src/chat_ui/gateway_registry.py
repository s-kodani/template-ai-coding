from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _iter_server_maps(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    gateways = data.get("gateways")
    if isinstance(gateways, list):
        maps: list[tuple[str, dict[str, Any]]] = []
        for gateway in gateways:
            if not isinstance(gateway, dict):
                continue
            servers = gateway.get("servers") or {}
            if isinstance(servers, dict):
                url = str(gateway.get("url") or "").strip().rstrip("/")
                maps.append((url, servers))
        return maps
    servers = data.get("servers") or {}
    return [("", servers)] if isinstance(servers, dict) else []


def load_ui_servers(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    listed: list[dict[str, Any]] = []
    for gateway_url, servers in _iter_server_maps(data):
        for server_id, server in servers.items():
            if not isinstance(server, dict) or not server.get("enabled", True):
                continue
            ui = server.get("ui") or {}
            allowed = list((server.get("authorization") or {}).get("allowed_tools") or [])
            listed.append(
                {
                    "id": server_id,
                    "name": str(ui.get("name") or server_id),
                    "tools": [{"name": str(name)} for name in allowed],
                    "gateway_url": gateway_url,
                }
            )
    return listed


def load_gateway_urls(path: Path) -> list[str]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    gateways = data.get("gateways")
    if not isinstance(gateways, list):
        return []
    urls: list[str] = []
    for gateway in gateways:
        if not isinstance(gateway, dict):
            continue
        url = str(gateway.get("url") or "").strip().rstrip("/")
        if url:
            urls.append(url)
    return urls


def load_name_index(path: Path) -> dict[str, str]:
    """Map registry ``ui.name`` to ``server_id`` for Gateway MCP connect routing."""
    return {str(entry["name"]): str(entry["id"]) for entry in load_ui_servers(path)}


def load_id_to_name(path: Path) -> dict[str, str]:
    """Map registry ``server_id`` to ``ui.name``."""
    return {str(entry["id"]): str(entry["name"]) for entry in load_ui_servers(path)}
