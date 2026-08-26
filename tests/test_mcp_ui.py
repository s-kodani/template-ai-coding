from __future__ import annotations

from pathlib import Path

from chat_ui.mcp_ui import (
    DEFAULT_MCP_NAME,
    default_mcp_ui_entry,
    render_mcp_autoload_js,
    upsert_mcp_ui_entry,
    write_mcp_autoload_script,
)


def test_default_mcp_ui_entry_is_user_provided_streamable_http() -> None:
    entry = default_mcp_ui_entry("http://mcp-server:8000/mcp")

    assert entry == {
        "name": DEFAULT_MCP_NAME,
        "tools": [],
        "clientType": "streamable-http",
        "url": "http://mcp-server:8000/mcp",
        "status": "disconnected",
        "isUserProvided": True,
    }
    assert "command" not in entry
    assert "headers" not in entry


def test_upsert_mcp_ui_entry_prepends_when_missing() -> None:
    extra = {
        "name": "other",
        "tools": [],
        "clientType": "sse",
        "url": "http://example/sse",
        "status": "connected",
    }

    merged = upsert_mcp_ui_entry([extra], default_mcp_ui_entry("http://mcp-server:8000/mcp"))

    assert [item["name"] for item in merged] == [DEFAULT_MCP_NAME, "other"]


def test_upsert_mcp_ui_entry_updates_url_and_keeps_other_fields() -> None:
    existing = [
        {
            "name": DEFAULT_MCP_NAME,
            "tools": [{"name": "search_knowledge"}],
            "clientType": "sse",
            "url": "http://localhost:8000/mcp",
            "headers": None,
            "status": "connected",
        }
    ]

    merged = upsert_mcp_ui_entry(existing, default_mcp_ui_entry("http://mcp-server:8000/mcp"))

    assert len(merged) == 1
    assert merged[0]["url"] == "http://mcp-server:8000/mcp"
    assert merged[0]["clientType"] == "streamable-http"
    assert merged[0]["isUserProvided"] is True
    assert merged[0]["tools"] == [{"name": "search_knowledge"}]
    assert merged[0]["status"] == "connected"
    assert "headers" not in merged[0]


def test_render_mcp_autoload_js_embeds_server_url() -> None:
    script = render_mcp_autoload_js("http://mcp-server:8000/mcp")

    assert "mcp_storage_key" in script
    assert "knowledge-mcp" in script
    assert "http://mcp-server:8000/mcp" in script
    assert "streamable-http" in script
    assert '"isUserProvided": true' in script
    assert "command" not in script
    assert '"headers"' not in script


def test_write_mcp_autoload_script_creates_public_js(tmp_path: Path) -> None:
    path = write_mcp_autoload_script(tmp_path, "http://mcp-server:8000/mcp")

    assert path == tmp_path / "mcp-autoload.js"
    assert "http://mcp-server:8000/mcp" in path.read_text(encoding="utf-8")
