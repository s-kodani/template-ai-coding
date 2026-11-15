from __future__ import annotations

import asyncio
import importlib.util

import pytest


def test_patched_mcp_client_keeps_result_and_injects_call_context(monkeypatch, tmp_path):
    from open_webui_ext import tracing
    from open_webui_ext.patch import patch_source

    monkeypatch.setattr(tracing, "inject_trace", lambda: {"traceparent": "00-trace-parent-01"})
    source = """from __future__ import annotations

class MCPClient:
    async def call_tool_raw(self, function_name: str, function_args: dict) -> dict:
        tool_call_timeout = 30
        result = await self.client.call_tool(function_name, function_args, read_timeout_seconds=tool_call_timeout)
        return result
"""
    patched = patch_source("utils/mcp/client.py", source)
    module_path = tmp_path / "patched_client.py"
    module_path.write_text(patched)
    spec = importlib.util.spec_from_file_location("patched_client", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    class Upstream:
        async def call_tool(self, name, arguments, **kwargs):
            captured.update(name=name, arguments=arguments, **kwargs)
            return {"structuredContent": {"hits": []}}

    client = module.MCPClient()
    client.client = Upstream()
    assert asyncio.run(client.call_tool_raw("search_knowledge", {"query": "test"})) == {
        "structuredContent": {"hits": []}
    }
    assert captured == {
        "name": "search_knowledge",
        "arguments": {"query": "test"},
        "read_timeout_seconds": 30,
        "meta": {"traceparent": "00-trace-parent-01"},
    }


def test_patch_rejects_changed_upstream_before_writing(tmp_path):
    from open_webui_ext.patch import patch_tree

    path = tmp_path / "main.py"
    path.write_text("# unrecognized upstream version\n")
    with pytest.raises(RuntimeError, match="Unsupported Open WebUI source"):
        patch_tree(tmp_path)
    assert path.read_text() == "# unrecognized upstream version\n"


def test_patch_rejects_duplicate_hook_instead_of_guessing():
    from open_webui_ext.patch import patch_source

    definition = "async def generate_chat_completion(\n"
    with pytest.raises(RuntimeError, match="one hook"):
        patch_source("utils/chat.py", definition + definition)
