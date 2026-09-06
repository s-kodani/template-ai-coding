from __future__ import annotations

from pathlib import Path

from chat_ui.gateway_registry import (
    load_gateway_urls,
    load_id_to_name,
    load_name_index,
    load_ui_servers,
)


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
            "gateway_url": "",
        },
        {"id": "other", "name": "other", "tools": [{"name": "ping"}], "gateway_url": ""},
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


def test_load_ui_servers_flattens_gateways_list(tmp_path: Path) -> None:
    path = tmp_path / "registry.yml"
    path.write_text(
        """
gateways:
  - url: http://gateway-a:8082
    servers:
      knowledge:
        enabled: true
        ui:
          name: knowledge-mcp
        authorization:
          allowed_tools: [search_knowledge]
      off:
        enabled: false
        ui:
          name: off-mcp
  - url: http://gateway-b:8083
    servers:
      extra:
        enabled: true
        ui:
          name: extra-mcp
        authorization:
          allowed_tools: [ping]
""",
        encoding="utf-8",
    )
    assert load_ui_servers(path) == [
        {
            "id": "knowledge",
            "name": "knowledge-mcp",
            "tools": [{"name": "search_knowledge"}],
            "gateway_url": "http://gateway-a:8082",
        },
        {
            "id": "extra",
            "name": "extra-mcp",
            "tools": [{"name": "ping"}],
            "gateway_url": "http://gateway-b:8083",
        },
    ]
    assert load_name_index(path) == {
        "knowledge-mcp": "knowledge",
        "extra-mcp": "extra",
    }


def test_load_gateway_urls_reads_each_gateway_url(tmp_path: Path) -> None:
    path = tmp_path / "registry.yml"
    path.write_text(
        """
gateways:
  - url: http://gateway-a:8082
    servers:
      knowledge:
        enabled: true
  - url: http://gateway-b:8083/
    servers:
      extra:
        enabled: true
  - servers:
      skipped:
        enabled: true
""",
        encoding="utf-8",
    )
    assert load_gateway_urls(path) == [
        "http://gateway-a:8082",
        "http://gateway-b:8083",
    ]


def test_load_gateway_urls_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_gateway_urls(tmp_path / "missing.yml") == []
