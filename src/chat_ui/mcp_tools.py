from __future__ import annotations

import json
from typing import Any, Literal

from knowledge_mcp.tracing import (
    inject_langfuse_propagated_meta,
    record_tool_output,
    tool_observation,
)

ToolTarget = tuple[Literal["gateway", "session", "unknown"], str | None]


def openai_tool_from_mcp(tool: dict[str, Any]) -> dict[str, Any]:
    schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "parameters": schema,
        },
    }


def collect_openai_tools(
    default_tools: list[dict[str, Any]],
    session_tools: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    seen = {tool["function"]["name"] for tool in default_tools}
    merged = list(default_tools)
    for tools in session_tools.values():
        for tool in tools:
            name = tool["name"]
            if name in seen:
                continue
            seen.add(name)
            merged.append(openai_tool_from_mcp(tool))
    return merged


def find_session_for_tool(
    name: str, session_tools: dict[str, list[dict[str, Any]]]
) -> str | None:
    for session_name, tools in session_tools.items():
        if any(tool["name"] == name for tool in tools):
            return session_name
    return None


def llm_tool_name(server_id: str, tool_name: str) -> str:
    return f"{server_id}__{tool_name}"


def filter_gateway_catalog(
    tools: list[dict[str, Any]],
    targets: dict[str, tuple[str, str]],
    enabled_server_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    kept = {
        name: ref for name, ref in targets.items() if ref[0] in enabled_server_ids
    }
    kept_tools = [
        tool for tool in tools if tool.get("function", {}).get("name") in kept
    ]
    return kept_tools, kept


def apply_gateway_toggle(
    catalog_tools: list[dict[str, Any]],
    catalog_targets: dict[str, tuple[str, str]],
    enabled: set[str] | None,
    server_id: str,
    enable: bool,
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]], set[str]]:
    current = (
        set(enabled)
        if enabled is not None
        else {ref[0] for ref in catalog_targets.values()}
    )
    if enable:
        current.add(server_id)
    else:
        current.discard(server_id)
    tools, targets = filter_gateway_catalog(catalog_tools, catalog_targets, current)
    return tools, targets, current


def catalog_from_listed_tools(
    servers: list[tuple[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str]]]:
    openai_tools: list[dict[str, Any]] = []
    targets: dict[str, tuple[str, str]] = {}
    for server_id, tools in servers:
        for tool in tools:
            mcp_name = tool.get("name")
            if not mcp_name:
                continue
            name = llm_tool_name(server_id, mcp_name)
            if name in targets:
                continue
            targets[name] = (server_id, mcp_name)
            openai_tools.append(openai_tool_from_mcp({**tool, "name": name}))
    return openai_tools, targets


def resolve_tool_target(
    name: str,
    session_tools: dict[str, list[dict[str, Any]]],
    gateway_targets: dict[str, str] | dict[str, tuple[str, str]] | None = None,
) -> ToolTarget:
    if gateway_targets and name in gateway_targets:
        mapped = gateway_targets[name]
        server_id = mapped[0] if isinstance(mapped, tuple) else mapped
        return ("gateway", server_id)
    session_name = find_session_for_tool(name, session_tools)
    if session_name is None:
        return ("unknown", None)
    return ("session", session_name)


def parse_tool_result(result: Any) -> dict[str, Any]:
    content = getattr(result, "content", None) or []
    text = ""
    if content:
        first = content[0]
        text = first.text if hasattr(first, "text") else str(first)

    if getattr(result, "isError", False) or getattr(result, "is_error", False):
        return {"error": text or "Tool returned an error."}
    if not content:
        return {"error": "Tool returned no content."}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"text": text}


async def call_session_tool(
    session: Any,
    name: str,
    arguments: dict[str, Any],
    *,
    tool_metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    with tool_observation(name, arguments, metadata=tool_metadata):
        result = await session.call_tool(
            name, arguments, meta=inject_langfuse_propagated_meta({})
        )
        output = parse_tool_result(result)
        record_tool_output(output)
    return output
