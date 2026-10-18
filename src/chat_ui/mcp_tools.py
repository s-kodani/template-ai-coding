from __future__ import annotations

import json
import re
from typing import Any, Literal

from knowledge_mcp.tracing import (
    inject_langfuse_propagated_meta,
    record_tool_output,
    tool_observation,
)

ToolChoice = dict[str, Any] | Literal["auto"]
ToolTarget = tuple[Literal["session", "unknown"], str | None]
_TOOL_URL = re.compile(r"https?://[^\s\"'\\]+")


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


def mcp_tool_description(mcp_name: str, description: str | None) -> str:
    lead = f"MCP tool {mcp_name}."
    cleaned = (description or "").strip()
    return f"{lead} {cleaned}" if cleaned else lead


def _tool_aliases(llm_name: str) -> set[str]:
    aliases = {llm_name}
    if "__" in llm_name:
        aliases.add(llm_name.split("__", 1)[1])
    return aliases


def select_tool_choice(tools: list[dict[str, Any]], user_text: str) -> ToolChoice:
    """Force the named function when the user mentions exactly one connected tool."""
    if not tools or not user_text:
        return "auto"
    hits: list[str] = []
    for tool in tools:
        name = str(tool.get("function", {}).get("name") or "")
        if name and any(alias and alias in user_text for alias in _tool_aliases(name)):
            hits.append(name)
    if len(hits) != 1:
        return "auto"
    return {"type": "function", "function": {"name": hits[0]}}


def tool_choice_label(tool_choice: ToolChoice) -> str:
    if isinstance(tool_choice, dict):
        return str(tool_choice.get("function", {}).get("name") or "auto")
    return str(tool_choice)


def merge_assistant_with_tool_facts(
    assistant_text: str, payloads: list[dict[str, Any]]
) -> str:
    """Append tool URLs and errors the model omitted from its reply."""
    facts: list[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        text = item.strip()
        if text and text not in seen:
            seen.add(text)
            facts.append(text)

    for payload in payloads:
        error = payload.get("error")
        if error:
            add(str(error))
        for url in _TOOL_URL.findall(json.dumps(payload, ensure_ascii=False)):
            add(url)

    missing = [fact for fact in facts if fact not in assistant_text]
    if not missing:
        return assistant_text
    return assistant_text.rstrip() + "\n" + "\n".join(missing)


def mcp_tool_name_from_llm(llm_name: str, server_id: str) -> str:
    prefix = f"{server_id}__"
    if llm_name.startswith(prefix):
        return llm_name[len(prefix) :]
    return llm_name


def prefix_tools_for_gateway(
    server_id: str, tools: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prefixed: list[dict[str, Any]] = []
    for tool in tools:
        mcp_name = tool.get("name")
        if not mcp_name:
            continue
        prefixed.append(
            {
                **tool,
                "name": llm_tool_name(server_id, str(mcp_name)),
                "description": mcp_tool_description(str(mcp_name), tool.get("description")),
            }
        )
    return prefixed


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
            openai_tools.append(
                openai_tool_from_mcp(
                    {
                        **tool,
                        "name": name,
                        "description": mcp_tool_description(
                            str(mcp_name), tool.get("description")
                        ),
                    }
                )
            )
    return openai_tools, targets


def resolve_tool_target(
    name: str,
    session_tools: dict[str, list[dict[str, Any]]],
) -> ToolTarget:
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
