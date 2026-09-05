from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from chat_ui.mcp_ui import (
    GATEWAY_MCP_TYPE,
    GATEWAY_MCP_URL_LABEL,
    render_mcp_autoload_js,
    write_mcp_autoload_script,
)

_SAMPLE_GATEWAY_NAME = "docs-mcp"
_SAMPLE_ENTRY = {
    "name": _SAMPLE_GATEWAY_NAME,
    "tools": [{"name": "search_docs"}, {"name": "get_document"}],
}

HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

const scriptPath = process.argv[2];
const script = fs.readFileSync(scriptPath, "utf8");

const store = {};
const fetchCalls = [];
const originalFetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  fetchCalls.push({
    url,
    method: init.method || "GET",
    body: init.body || null,
  });
  if (String(url).includes("/gateway-mcp")) {
    const payload = JSON.parse(init.body || "{}");
    if ((init.method || "GET").toUpperCase() === "DELETE") {
      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response(JSON.stringify({
      success: true,
      mcp: {
        name: payload.name,
        tools: [{ name: "search_docs" }, { name: "get_document" }],
        clientType: "gateway",
        url: "via MCP Gateway",
      },
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  return new Response(JSON.stringify({ proxied: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};

const sandbox = {
  window: {},
  location: { origin: "http://localhost:8080" },
  localStorage: {
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, value) => {
      store[key] = String(value);
    },
  },
  fetch: originalFetch,
  Response,
  URL,
  JSON,
  Promise,
  console,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

store.mcp_storage_key = JSON.stringify([
  {
    name: "docs-mcp",
    tools: [],
    status: "failed",
    clientType: "streamable-http",
    url: "http://mcp-server:8000/mcp",
    isUserProvided: true,
  },
  {
    name: "other-mcp",
    tools: [{ name: "ping" }],
    status: "connected",
    clientType: "streamable-http",
    url: "http://localhost:9000/mcp",
    isUserProvided: true,
  },
]);

vm.runInNewContext(script, sandbox);

(async () => {
  const stored = JSON.parse(store.mcp_storage_key);
  const gateway = await sandbox.fetch("http://localhost:8080/mcp", {
    method: "POST",
    body: JSON.stringify({ sessionId: "s", name: "docs-mcp" }),
  });
  const polluted = await sandbox.fetch("http://localhost:8080/mcp", {
    method: "POST",
    body: JSON.stringify({
      sessionId: "s2",
      name: "docs-mcp",
      clientType: "gateway",
      url: "via MCP Gateway",
      isUserProvided: false,
    }),
  });
  const other = await sandbox.fetch("http://localhost:8080/mcp", {
    method: "POST",
    body: JSON.stringify({ sessionId: "s", name: "other-mcp", url: "http://localhost:9000/mcp" }),
  });
  const removed = await sandbox.fetch("http://localhost:8080/mcp", {
    method: "DELETE",
    body: JSON.stringify({ sessionId: "s", name: "docs-mcp" }),
  });
  const result = {
    stored,
    gateway: await gateway.json(),
    polluted: await polluted.json(),
    other: await other.json(),
    removed: await removed.json(),
    fetchCalls,
  };
  process.stdout.write(JSON.stringify(result));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
"""


def test_render_mcp_autoload_js_seeds_gateway_display_entry() -> None:
    script = render_mcp_autoload_js([_SAMPLE_ENTRY])

    assert "mcp_storage_key" in script
    assert _SAMPLE_GATEWAY_NAME in script
    assert "unshift" in script
    assert GATEWAY_MCP_TYPE in script
    assert GATEWAY_MCP_URL_LABEL in script
    assert "search_docs" in script
    assert "get_document" in script
    assert "http://mcp-server" not in script
    assert "Authorization" not in script
    assert "streamable-http" not in script


def test_write_mcp_autoload_script_creates_public_js(tmp_path: Path) -> None:
    path = write_mcp_autoload_script(tmp_path, [_SAMPLE_ENTRY])

    assert path == tmp_path / "mcp-autoload.js"
    assert _SAMPLE_GATEWAY_NAME in path.read_text(encoding="utf-8")
    assert GATEWAY_MCP_TYPE in path.read_text(encoding="utf-8")


def test_autoload_script_replaces_legacy_entry_and_intercepts_gateway_mcp(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        node = "/exec-daemon/node"
    if not Path(node).exists():
        raise RuntimeError("node is required to execute mcp-autoload.js")

    script_path = write_mcp_autoload_script(tmp_path, [_SAMPLE_ENTRY])
    harness_path = tmp_path / "harness.js"
    harness_path.write_text(HARNESS, encoding="utf-8")

    completed = subprocess.run(
        [node, str(harness_path), str(script_path)],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "NODE_PATH": ""},
    )
    result = json.loads(completed.stdout)
    stored = result["stored"]
    names = [item["name"] for item in stored]

    assert names.count(_SAMPLE_GATEWAY_NAME) == 1
    assert "other-mcp" in names
    gateway = next(item for item in stored if item["name"] == _SAMPLE_GATEWAY_NAME)
    assert gateway["status"] == "connected"
    assert gateway["type"] == GATEWAY_MCP_TYPE
    assert gateway["url"] == GATEWAY_MCP_URL_LABEL
    assert gateway["isUserProvided"] is False
    assert [tool["name"] for tool in gateway["tools"]] == [
        "search_docs",
        "get_document",
    ]
    assert gateway.get("headers") in (None, {})
    assert "clientType" not in gateway

    assert result["gateway"]["success"] is True
    assert result["polluted"]["success"] is True
    assert result["gateway"]["mcp"]["name"] == _SAMPLE_GATEWAY_NAME
    assert result["removed"]["success"] is True
    assert result["other"] == {"proxied": True}
    assert result["gateway"]["mcp"]["clientType"] == GATEWAY_MCP_TYPE
    assert [call["url"] for call in result["fetchCalls"]] == [
        "http://localhost:8080/gateway-mcp",
        "http://localhost:8080/gateway-mcp",
        "http://localhost:8080/mcp",
        "http://localhost:8080/gateway-mcp",
    ]
    assert result["fetchCalls"][0]["method"] == "POST"
    assert result["fetchCalls"][2]["method"] == "POST"
    assert result["fetchCalls"][3]["method"] == "DELETE"
    assert json.loads(result["fetchCalls"][0]["body"]) == {
        "sessionId": "s",
        "name": "docs-mcp",
    }
    assert json.loads(result["fetchCalls"][1]["body"]) == {
        "sessionId": "s2",
        "name": "docs-mcp",
    }
    forwarded = result["fetchCalls"][2]
    assert forwarded["method"] == "POST"
    assert json.loads(forwarded["body"]) == {
        "sessionId": "s",
        "name": "other-mcp",
        "url": "http://localhost:9000/mcp",
    }


def test_render_mcp_autoload_js_includes_all_gateway_entries() -> None:
    script = render_mcp_autoload_js(
        [
            {"name": "docs-mcp", "tools": [{"name": "search_docs"}]},
            {"name": "other", "tools": [{"name": "ping"}]},
        ]
    )
    assert script.count("unshift") == 1
    assert "docs-mcp" in script
    assert "other" in script
    assert "ping" in script
