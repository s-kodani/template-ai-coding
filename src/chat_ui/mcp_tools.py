from __future__ import annotations

import json
from typing import Any, Literal

from knowledge_mcp.tracing import inject_langfuse_propagated_meta, tool_observation

DEFAULT_TOOL_NAMES = frozenset({"search_knowledge", "get_document"})

ToolTarget = tuple[Literal["default", "session", "unknown"], str | None]


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


def resolve_tool_target(
    name: str, session_tools: dict[str, list[dict[str, Any]]]
) -> ToolTarget:
    if name in DEFAULT_TOOL_NAMES:
        return ("default", None)
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

    if getattr(result, "isError", False):
        return {"error": text or "Tool returned an error."}
    if not content:
        return {"error": "Tool returned no content."}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"text": text}


async def call_session_tool(
    session: Any, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    with tool_observation(name, arguments):
        result = await session.call_tool(
            name, arguments, meta=inject_langfuse_propagated_meta({})
        )
    return parse_tool_result(result)
