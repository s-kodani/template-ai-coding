from __future__ import annotations

from pathlib import Path

from chat_ui.gateway_registry import load_id_to_name, load_name_index, load_ui_servers


def test_load_ui_servers_skips_disabled_and_uses_ui_name(tmp_path: Path) -> None:
    path = tmp_path / "registry.yml"
    path.write_text(
        """
servers:
  knowledge:
    enabled: true
    ui:
      name: knowledge-mcp
    authorization:
      allowed_tools:
        - search_knowledge
        - get_document
  other:
    enabled: true
    authorization:
      allowed_tools:
        - ping
  off:
    enabled: false
    authorization:
      allowed_tools:
        - hidden
""",
        encoding="utf-8",
    )

    assert load_ui_servers(path) == [
        {
            "id": "knowledge",
            "name": "knowledge-mcp",
            "tools": [{"name": "search_knowledge"}, {"name": "get_document"}],
        },
        {"id": "other", "name": "other", "tools": [{"name": "ping"}]},
    ]


def test_load_ui_servers_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_ui_servers(tmp_path / "missing.yml") == []


def test_load_name_index_maps_ui_name_to_server_id(tmp_path: Path) -> None:
    registry = tmp_path / "gateway-registry.yml"
    registry.write_text(
        """
servers:
  knowledge:
    enabled: true
    ui:
      name: knowledge-mcp
    authorization:
      allowed_tools: [search_knowledge]
  other:
    enabled: false
    ui:
      name: other-mcp
""",
        encoding="utf-8",
    )
    assert load_name_index(registry) == {"knowledge-mcp": "knowledge"}
    assert load_id_to_name(registry) == {"knowledge": "knowledge-mcp"}
