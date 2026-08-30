from __future__ import annotations

from chat_ui.gateway_session import apply_ui_gateway_toggle
from chat_ui.mcp_tools import catalog_from_listed_tools


def test_apply_ui_gateway_toggle_updates_session_store() -> None:
    tools, targets = catalog_from_listed_tools(
        [
            ("knowledge", [{"name": "search_knowledge", "inputSchema": {}}]),
            ("other", [{"name": "ping", "inputSchema": {}}]),
        ]
    )
    store = {
        "gateway_catalog_tools": tools,
        "gateway_catalog_targets": targets,
        "gateway_enabled": None,
    }
    names = {"knowledge-mcp": "knowledge", "other": "other"}

    disconnect = apply_ui_gateway_toggle(
        store, ui_name="knowledge-mcp", enable=False, name_to_id=names
    )
    assert disconnect["success"] is True
    assert [tool["function"]["name"] for tool in store["gateway_tools"]] == [
        "other__ping"
    ]
    assert store["gateway_enabled"] == ["other"]
    assert store["gateway_disabled"] == ["knowledge"]

    connect = apply_ui_gateway_toggle(
        store, ui_name="knowledge-mcp", enable=True, name_to_id=names
    )
    assert connect["success"] is True
    assert connect["mcp"]["name"] == "knowledge-mcp"
    assert [tool["function"]["name"] for tool in store["gateway_tools"]] == [
        "knowledge__search_knowledge",
        "other__ping",
    ]


def test_apply_ui_gateway_toggle_disable_before_catalog_is_kept() -> None:
    names = {"knowledge-mcp": "knowledge", "other": "other"}
    store: dict = {}
    apply_ui_gateway_toggle(
        store, ui_name="knowledge-mcp", enable=False, name_to_id=names
    )
    assert store["gateway_disabled"] == ["knowledge"]
    tools, targets = catalog_from_listed_tools(
        [
            ("knowledge", [{"name": "search_knowledge", "inputSchema": {}}]),
            ("other", [{"name": "ping", "inputSchema": {}}]),
        ]
    )
    store["gateway_catalog_tools"] = tools
    store["gateway_catalog_targets"] = targets
    apply_ui_gateway_toggle(store, ui_name="other", enable=True, name_to_id=names)
    assert [tool["function"]["name"] for tool in store["gateway_tools"]] == [
        "other__ping"
    ]


def test_apply_ui_gateway_toggle_unknown_name() -> None:
    result = apply_ui_gateway_toggle(
        {}, ui_name="missing", enable=False, name_to_id={"docs-mcp": "docs"}
    )
    assert result == {"success": False, "error": "UNKNOWN_GATEWAY_MCP"}
