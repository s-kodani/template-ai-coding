from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MCP_NAME = "knowledge-mcp"
MCP_STORAGE_KEY = "mcp_storage_key"


def default_mcp_ui_entry(url: str) -> dict[str, Any]:
    return {
        "name": DEFAULT_MCP_NAME,
        "tools": [],
        "clientType": "streamable-http",
        "url": url,
        "status": "disconnected",
        "isUserProvided": True,
    }


def upsert_mcp_ui_entry(
    stored: list[dict[str, Any]], entry: dict[str, Any]
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in stored]
    for item in merged:
        if item.get("name") == entry["name"]:
            item["url"] = entry["url"]
            item["clientType"] = entry["clientType"]
            item["isUserProvided"] = entry["isUserProvided"]
            item.pop("command", None)
            if item.get("headers") is None:
                item.pop("headers", None)
            return merged
    return [entry, *merged]


def render_mcp_autoload_js(url: str) -> str:
    entry = default_mcp_ui_entry(url)
    return f"""(() => {{
  const KEY = {json.dumps(MCP_STORAGE_KEY)};
  const DEFAULT_MCP = {json.dumps(entry, ensure_ascii=False)};
  let stored = [];
  try {{
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    stored = Array.isArray(parsed) ? parsed : [];
  }} catch (_error) {{
    stored = [];
  }}
  stored.forEach((item) => {{
    if (item && item.headers == null) {{
      delete item.headers;
    }}
  }});
  const index = stored.findIndex((item) => item && item.name === DEFAULT_MCP.name);
  if (index === -1) {{
    stored.unshift(DEFAULT_MCP);
  }} else {{
    stored[index] = {{
      ...stored[index],
      url: DEFAULT_MCP.url,
      clientType: DEFAULT_MCP.clientType,
      isUserProvided: DEFAULT_MCP.isUserProvided,
    }};
    if (stored[index].headers == null) {{
      delete stored[index].headers;
    }}
  }}
  localStorage.setItem(KEY, JSON.stringify(stored));
}})();
"""


def write_mcp_autoload_script(public_dir: Path, url: str) -> Path:
    public_dir.mkdir(parents=True, exist_ok=True)
    path = public_dir / "mcp-autoload.js"
    path.write_text(render_mcp_autoload_js(url), encoding="utf-8")
    return path
