from __future__ import annotations

from pathlib import Path

from chat_ui.mcp_ui import (
    DEFAULT_MCP_NAME,
    render_mcp_autoload_js,
    write_mcp_autoload_script,
)


def test_render_mcp_autoload_js_removes_knowledge_mcp() -> None:
    script = render_mcp_autoload_js()

    assert "mcp_storage_key" in script
    assert DEFAULT_MCP_NAME in script
    assert "filter" in script
    assert "unshift" not in script
    assert "http://mcp-server" not in script
    assert "streamable-http" not in script


def test_write_mcp_autoload_script_creates_public_js(tmp_path: Path) -> None:
    path = write_mcp_autoload_script(tmp_path)

    assert path == tmp_path / "mcp-autoload.js"
    assert DEFAULT_MCP_NAME in path.read_text(encoding="utf-8")
