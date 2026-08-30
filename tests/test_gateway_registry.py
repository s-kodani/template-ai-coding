from __future__ import annotations

from pathlib import Path

from chat_ui.gateway_registry import load_ui_servers


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
            "name": "knowledge-mcp",
            "tools": [{"name": "search_knowledge"}, {"name": "get_document"}],
        },
        {"name": "other", "tools": [{"name": "ping"}]},
    ]


def test_load_ui_servers_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_ui_servers(tmp_path / "missing.yml") == []
