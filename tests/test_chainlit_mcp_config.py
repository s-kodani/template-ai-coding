from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / ".chainlit" / "config.toml"
LEGACY_MCP_TABLES = ("sse", "stdio", "streamable-http")
EXPECTED_ALLOWED_URLS = {
    "http://mcp-server:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://host.docker.internal:8000",
}


def _mcp_settings() -> dict:
    with CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)["features"]["mcp"]


def test_mcp_config_rejects_legacy_transport_tables() -> None:
    mcp = _mcp_settings()

    for table in LEGACY_MCP_TABLES:
        assert table not in mcp


def test_mcp_user_servers_allowlist_covers_local_template_origins() -> None:
    user_servers = _mcp_settings()["user_servers"]

    assert user_servers["enabled"] is True
    assert set(user_servers["allowed_urls"]) == EXPECTED_ALLOWED_URLS


def test_mcp_enabled_without_named_stdio_servers() -> None:
    mcp = _mcp_settings()

    assert mcp["enabled"] is True
    servers = mcp.get("servers", [])
    assert all(server.get("type") != "stdio" for server in servers)
