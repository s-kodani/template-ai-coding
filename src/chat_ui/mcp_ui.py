from __future__ import annotations

import json
from pathlib import Path

DEFAULT_MCP_NAME = "knowledge-mcp"
MCP_STORAGE_KEY = "mcp_storage_key"


def render_mcp_autoload_js() -> str:
    """Remove the former knowledge-mcp autoload entry so Chainlit UI does not connect without a token."""
    return f"""(() => {{
  const KEY = {json.dumps(MCP_STORAGE_KEY)};
  const NAME = {json.dumps(DEFAULT_MCP_NAME)};
  let stored = [];
  try {{
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    stored = Array.isArray(parsed) ? parsed : [];
  }} catch (_error) {{
    stored = [];
  }}
  stored = stored.filter((item) => !(item && item.name === NAME));
  localStorage.setItem(KEY, JSON.stringify(stored));
}})();
"""


def write_mcp_autoload_script(public_dir: Path) -> Path:
    public_dir.mkdir(parents=True, exist_ok=True)
    path = public_dir / "mcp-autoload.js"
    path.write_text(render_mcp_autoload_js(), encoding="utf-8")
    return path
