from __future__ import annotations

from typing import Any

from chat_ui.mcp_tools import filter_gateway_catalog


def apply_ui_gateway_toggle(
    store: dict[str, Any],
    *,
    ui_name: str,
    enable: bool,
    name_to_id: dict[str, str],
) -> dict[str, Any]:
    server_id = name_to_id.get(ui_name)
    if not server_id:
        return {"success": False, "error": "UNKNOWN_GATEWAY_MCP"}
    disabled = set(store.get("gateway_disabled") or set())
    if enable:
        disabled.discard(server_id)
    else:
        disabled.add(server_id)
    catalog_tools = store.get("gateway_catalog_tools") or []
    catalog_targets = store.get("gateway_catalog_targets") or {}
    enabled = {ref[0] for ref in catalog_targets.values()} - disabled
    tools, targets = filter_gateway_catalog(catalog_tools, catalog_targets, enabled)
    store["gateway_tools"] = tools
    store["gateway_targets"] = targets
    store["gateway_enabled"] = sorted(enabled)
    store["gateway_disabled"] = sorted(disabled)
    if not enable:
        return {"success": True}
    catalog_targets = store.get("gateway_catalog_targets") or {}
    mcp_tools = [
        {"name": mcp_name}
        for llm_name, (sid, mcp_name) in catalog_targets.items()
        if sid == server_id
    ]
    return {
        "success": True,
        "mcp": {
            "name": ui_name,
            "tools": mcp_tools,
            "clientType": "gateway",
            "url": "via MCP Gateway",
        },
    }
