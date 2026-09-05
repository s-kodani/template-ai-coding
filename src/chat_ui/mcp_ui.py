from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MCP_STORAGE_KEY = "mcp_storage_key"
GATEWAY_MCP_TYPE = "gateway"
GATEWAY_MCP_URL_LABEL = "via MCP Gateway"


def _display_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    displayed: list[dict[str, Any]] = []
    for entry in entries:
        name = entry.get("name")
        if not name:
            continue
        displayed.append(
            {
                "name": name,
                "tools": entry.get("tools") or [],
                "type": GATEWAY_MCP_TYPE,
                "url": GATEWAY_MCP_URL_LABEL,
                "isUserProvided": False,
            }
        )
    return displayed


def render_mcp_autoload_js(entries: list[dict[str, Any]] | None = None) -> str:
    """Seed Gateway MCPs in Chainlit's MCP list for display; connect uses POST /mcp."""
    displayed = _display_entries(entries or [])
    names = [item["name"] for item in displayed]
    return f"""(() => {{
  const KEY = {json.dumps(MCP_STORAGE_KEY)};
  const ENTRIES = {json.dumps(displayed)};
  const NAMES = new Set({json.dumps(names)});
  let stored = [];
  try {{
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    stored = Array.isArray(parsed) ? parsed : [];
  }} catch (_error) {{
    stored = [];
  }}
  stored = stored.filter((item) => !(item && NAMES.has(item.name)));
  for (let i = ENTRIES.length - 1; i >= 0; i -= 1) {{
    stored.unshift(ENTRIES[i]);
  }}
  localStorage.setItem(KEY, JSON.stringify(stored));
}})();
"""


def write_mcp_autoload_script(
    public_dir: Path,
    entries: list[dict[str, Any]] | None = None,
) -> Path:
    public_dir.mkdir(parents=True, exist_ok=True)
    path = public_dir / "mcp-autoload.js"
    path.write_text(render_mcp_autoload_js(entries), encoding="utf-8")
    return path
