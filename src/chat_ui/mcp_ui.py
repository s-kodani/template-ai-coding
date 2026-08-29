from __future__ import annotations

import json
from pathlib import Path

DEFAULT_MCP_NAME = "knowledge-mcp"
MCP_STORAGE_KEY = "mcp_storage_key"
GATEWAY_MCP_TYPE = "gateway"
GATEWAY_MCP_URL_LABEL = "via MCP Gateway"

_GATEWAY_ENTRY = {
    "name": DEFAULT_MCP_NAME,
    "tools": [{"name": "search_knowledge"}, {"name": "get_document"}],
    "status": "connected",
    "type": GATEWAY_MCP_TYPE,
    "clientType": GATEWAY_MCP_TYPE,
    "url": GATEWAY_MCP_URL_LABEL,
    "isUserProvided": False,
}


def render_mcp_autoload_js() -> str:
    """Show knowledge-mcp in Chainlit's MCP list without opening a real session.

    Chainlit reconnects every Recoil MCP row with POST /mcp. There is no
    display-only API, so this script seeds localStorage and answers /mcp for
    this name locally. Tool calls still go through MCP Gateway.
    """
    return f"""(() => {{
  const KEY = {json.dumps(MCP_STORAGE_KEY)};
  const NAME = {json.dumps(DEFAULT_MCP_NAME)};
  const ENTRY = {json.dumps(_GATEWAY_ENTRY)};
  let stored = [];
  try {{
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    stored = Array.isArray(parsed) ? parsed : [];
  }} catch (_error) {{
    stored = [];
  }}
  stored = stored.filter((item) => !(item && item.name === NAME));
  stored.unshift(ENTRY);
  localStorage.setItem(KEY, JSON.stringify(stored));

  const originalFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {{
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const method = (
      (init && init.method) ||
      (typeof input === "object" && input && input.method) ||
      "GET"
    ).toUpperCase();
    let pathname = "";
    try {{
      pathname = new URL(url, location.origin).pathname;
    }} catch (_error) {{
      pathname = "";
    }}
    const isMcp = pathname === "/mcp" || pathname === "/mcp/";
    const body = init && init.body;
    if (isMcp && (method === "POST" || method === "DELETE") && typeof body === "string") {{
      try {{
        const payload = JSON.parse(body);
        if (payload && payload.name === NAME) {{
          if (method === "DELETE") {{
            return Promise.resolve(new Response(JSON.stringify({{ success: true }}), {{
              status: 200,
              headers: {{ "Content-Type": "application/json" }},
            }}));
          }}
          return Promise.resolve(new Response(JSON.stringify({{
            success: true,
            mcp: {{
              name: NAME,
              tools: ENTRY.tools,
              clientType: ENTRY.clientType,
              url: ENTRY.url,
            }},
          }}), {{
            status: 200,
            headers: {{ "Content-Type": "application/json" }},
          }}));
        }}
      }} catch (_error) {{}}
    }}
    return originalFetch(input, init);
  }};
}})();
"""


def write_mcp_autoload_script(public_dir: Path) -> Path:
    public_dir.mkdir(parents=True, exist_ok=True)
    path = public_dir / "mcp-autoload.js"
    path.write_text(render_mcp_autoload_js(), encoding="utf-8")
    return path
