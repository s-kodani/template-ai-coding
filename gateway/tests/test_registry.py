from __future__ import annotations

from pathlib import Path

from mcp_gateway.registry import load_registry


def test_load_registry_selects_gateway_by_public_base_url(tmp_path: Path) -> None:
    path = tmp_path / "registry.yml"
    path.write_text(
        """
gateways:
  - url: http://gateway-a:8082
    servers:
      knowledge:
        enabled: true
  - url: http://gateway-b:8083
    servers:
      extra:
        enabled: true
""",
        encoding="utf-8",
    )
    assert set(load_registry(path, public_base_url="http://gateway-b:8083/")) == {"extra"}


def test_load_registry_uses_single_gateway_when_url_unmatched(tmp_path: Path) -> None:
    path = tmp_path / "registry.yml"
    path.write_text(
        """
gateways:
  - url: http://mcp-gateway:8082
    servers:
      knowledge:
        enabled: true
""",
        encoding="utf-8",
    )
    assert set(load_registry(path, public_base_url="http://other:1")) == {"knowledge"}


def test_load_registry_keeps_top_level_servers(tmp_path: Path) -> None:
    path = tmp_path / "registry.yml"
    path.write_text(
        """
servers:
  knowledge:
    enabled: true
""",
        encoding="utf-8",
    )
    assert set(load_registry(path)) == {"knowledge"}
