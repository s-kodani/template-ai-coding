from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_ui_servers(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    servers = data.get("servers") or {}
    if not isinstance(servers, dict):
        return []
    listed: list[dict[str, Any]] = []
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
            }
        )
    return listed


def load_name_index(path: Path) -> dict[str, str]:
    """Map registry ``ui.name`` to ``server_id`` for Gateway MCP connect routing."""
    return {str(entry["name"]): str(entry["id"]) for entry in load_ui_servers(path)}


def load_id_to_name(path: Path) -> dict[str, str]:
    """Map registry ``server_id`` to ``ui.name``."""
    return {str(entry["id"]): str(entry["name"]) for entry in load_ui_servers(path)}
