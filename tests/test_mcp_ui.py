from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from chat_ui.mcp_ui import (
    DEFAULT_MCP_NAME,
    GATEWAY_MCP_TYPE,
    GATEWAY_MCP_URL_LABEL,
    render_mcp_autoload_js,
    write_mcp_autoload_script,
)

HARNESS = r"""
const fs = require("fs");
const vm = require("vm");

const scriptPath = process.argv[2];
const script = fs.readFileSync(scriptPath, "utf8");

const store = {};
const fetchCalls = [];
const originalFetch = async (input, init = {}) => {
  fetchCalls.push({
    url: typeof input === "string" ? input : input.url,
    method: init.method || "GET",
    body: init.body || null,
  });
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
    name: "knowledge-mcp",
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
    body: JSON.stringify({ sessionId: "s", name: "knowledge-mcp" }),
  });
  const other = await sandbox.fetch("http://localhost:8080/mcp", {
    method: "POST",
    body: JSON.stringify({ sessionId: "s", name: "other-mcp", url: "http://localhost:9000/mcp" }),
  });
  const removed = await sandbox.fetch("http://localhost:8080/mcp", {
    method: "DELETE",
    body: JSON.stringify({ sessionId: "s", name: "knowledge-mcp" }),
  });
  const result = {
    stored,
    gateway: await gateway.json(),
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
    script = render_mcp_autoload_js()

    assert "mcp_storage_key" in script
    assert DEFAULT_MCP_NAME in script
    assert "unshift" in script
    assert GATEWAY_MCP_TYPE in script
    assert GATEWAY_MCP_URL_LABEL in script
    assert "search_knowledge" in script
    assert "get_document" in script
    assert "http://mcp-server" not in script
    assert "Authorization" not in script
    assert "streamable-http" not in script


def test_write_mcp_autoload_script_creates_public_js(tmp_path: Path) -> None:
    path = write_mcp_autoload_script(tmp_path)

    assert path == tmp_path / "mcp-autoload.js"
    assert DEFAULT_MCP_NAME in path.read_text(encoding="utf-8")
    assert GATEWAY_MCP_TYPE in path.read_text(encoding="utf-8")


def test_autoload_script_replaces_legacy_entry_and_intercepts_knowledge_mcp(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    if node is None:
        node = "/exec-daemon/node"
    if not Path(node).exists():
        raise RuntimeError("node is required to execute mcp-autoload.js")

    script_path = write_mcp_autoload_script(tmp_path)
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

    assert names.count(DEFAULT_MCP_NAME) == 1
    assert "other-mcp" in names
    gateway = next(item for item in stored if item["name"] == DEFAULT_MCP_NAME)
    assert gateway["status"] == "connected"
    assert gateway["type"] == GATEWAY_MCP_TYPE
    assert gateway["url"] == GATEWAY_MCP_URL_LABEL
    assert gateway["isUserProvided"] is False
    assert [tool["name"] for tool in gateway["tools"]] == [
        "search_knowledge",
        "get_document",
    ]
    assert gateway.get("headers") in (None, {})

    assert result["gateway"]["success"] is True
    assert result["gateway"]["mcp"]["name"] == DEFAULT_MCP_NAME
    assert result["removed"]["success"] is True
    assert result["other"] == {"proxied": True}
    assert len(result["fetchCalls"]) == 1
    forwarded = result["fetchCalls"][0]
    assert forwarded["url"] == "http://localhost:8080/mcp"
    assert forwarded["method"] == "POST"
    assert json.loads(forwarded["body"]) == {
        "sessionId": "s",
        "name": "other-mcp",
        "url": "http://localhost:9000/mcp",
    }
