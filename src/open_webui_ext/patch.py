"""Apply four tracing hooks only to the audited Open WebUI v0.13.0 source."""

from __future__ import annotations

import argparse
import ast
import hashlib
from pathlib import Path

SOURCE_HASHES = {
    "main.py": "3d36935b716d396156d026d7d97e0f1c8e34351883721e08389ab207803e757b",
    "utils/chat.py": "c897d17e9fd1dd15682268a1577bd7297a1c0ae0ea2d2ea77ecae71c245636ac",
    "utils/mcp/client.py": "ce99c883a9226a1a48adf427bd3dca2c8925711cf89be3de78beac56e7cc8af9",
    "routers/tools.py": "424af44005793e76276f304132150a48abb774c35f2ed2657ac7be62542e89fa",
}

HOOKS = {
    "main.py": (
        "from open_webui_ext.tracing import trace_chat_turn as _trace_chat_turn\n",
        [
            (
                "    async def process_chat(request, form_data, user, metadata, model, tasks=None):\n",
                "    @_trace_chat_turn\n    async def process_chat(request, form_data, user, metadata, model, tasks=None):\n",
            )
        ],
    ),
    "utils/chat.py": (
        "from open_webui_ext.tracing import trace_generation as _trace_generation\n",
        [
            (
                "async def generate_chat_completion(\n",
                "@_trace_generation\nasync def generate_chat_completion(\n",
            )
        ],
    ),
    "utils/mcp/client.py": (
        "from open_webui_ext.tracing import inject_trace as _inject_trace, trace_mcp_tool as _trace_mcp_tool\n",
        [
            (
                "    async def call_tool_raw(self, function_name: str, function_args: dict) -> dict:\n",
                "    @_trace_mcp_tool\n    async def call_tool_raw(self, function_name: str, function_args: dict) -> dict:\n",
            ),
            (
                "result = await self.client.call_tool(function_name, function_args, read_timeout_seconds=tool_call_timeout)",
                "result = await self.client.call_tool(function_name, function_args, read_timeout_seconds=tool_call_timeout, meta=_inject_trace())",
            ),
        ],
    ),
    "routers/tools.py": (
        "from open_webui_ext.tracing import trace_app_rpc as _trace_app_rpc\n",
        [
            (
                "async def mcp_app_rpc(request: Request, id: str, form_data: MCPAppRPCForm, user=Depends(get_verified_user)):\n",
                "@_trace_app_rpc\nasync def mcp_app_rpc(request: Request, id: str, form_data: MCPAppRPCForm, user=Depends(get_verified_user)):\n",
            )
        ],
    ),
}


def patch_source(name: str, source: str) -> str:
    prefix, replacements = HOOKS[name]
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"Expected one hook in {name}")
        source = source.replace(old, new, 1)
    tree = ast.parse(source, filename=name)
    insert_after = 0
    for node in tree.body:
        if (isinstance(node, ast.ImportFrom) and node.module == "__future__") or (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and insert_after == 0
        ):
            insert_after = node.end_lineno
        else:
            break
    lines = source.splitlines(keepends=True)
    result = "".join(lines[:insert_after]) + prefix + "".join(lines[insert_after:])
    compile(result, name, "exec")
    return result


def patch_tree(root: Path) -> None:
    patched = {}
    for name, expected in SOURCE_HASHES.items():
        path = root / name
        if not path.is_file():
            raise RuntimeError(f"Unsupported Open WebUI source: {name} missing")
        source = path.read_text().rstrip("\n") + "\n"
        if hashlib.sha256(source.encode()).hexdigest() != expected:
            raise RuntimeError(f"Unsupported Open WebUI source: {name} hash mismatch")
        patched[path] = patch_source(name, source)
    # Validate the complete source set before changing any file.
    for path, source in patched.items():
        path.write_text(source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    patch_tree(args.root)
    print("Applied tracing hooks to Open WebUI v0.13.0")


if __name__ == "__main__":
    main()
