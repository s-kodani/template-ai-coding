from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import chainlit as cl
from langfuse import observe

from chat_ui.auth import register_oauth_callback
from chat_ui.mcp_bridge import GET_DOCUMENT_TOOL, SEARCH_TOOL, MCPBridge, build_openai_client
from chat_ui.mcp_tools import call_session_tool, collect_openai_tools, resolve_tool_target
from chat_ui.mcp_ui import write_mcp_autoload_script
from knowledge_mcp.config import get_settings
from knowledge_mcp.tracing import configure_langfuse_tracing, instrument_asyncpg

_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

settings = get_settings()
openai_client = build_openai_client(settings)
mcp_bridge = MCPBridge(settings)
write_mcp_autoload_script(Path.cwd() / "public", settings.mcp_server_url)
register_oauth_callback()

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a local knowledge base "
    "and any MCP tools the user has connected in this session. "
    "Use search_knowledge when the user asks about project documentation. "
    "Use other connected tools when they match the request. "
    "Cite document titles and ids from knowledge-base tool results."
)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("messages", [{"role": "system", "content": SYSTEM_PROMPT}])
    cl.user_session.set("mcp_tools", {})


@cl.on_mcp_connect
async def on_mcp_connect(connection: Any, session: Any) -> None:
    result = await session.list_tools()
    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.inputSchema,
        }
        for tool in result.tools
    ]
    mcp_tools = cl.user_session.get("mcp_tools") or {}
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)


@cl.on_mcp_disconnect
async def on_mcp_disconnect(name: str, _session: Any) -> None:
    mcp_tools = cl.user_session.get("mcp_tools") or {}
    mcp_tools.pop(name, None)
    cl.user_session.set("mcp_tools", mcp_tools)


def _llm_tools() -> list[dict[str, Any]]:
    return collect_openai_tools(
        [SEARCH_TOOL, GET_DOCUMENT_TOOL],
        cl.user_session.get("mcp_tools") or {},
    )


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    session_tools = cl.user_session.get("mcp_tools") or {}
    kind, session_name = resolve_tool_target(name, session_tools)
    if kind == "default":
        return await mcp_bridge.call_tool(name, arguments)
    if kind == "session" and session_name:
        entry = cl.context.session.mcp_sessions.get(session_name)
        if not entry:
            return {"error": f"MCP session not found: {session_name}"}
        mcp_session, _ = entry
        return await call_session_tool(mcp_session, name, arguments)
    return {"error": f"Unknown tool: {name}"}


@observe(name="llm.generate")
async def _generate(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
    return await openai_client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )


@cl.on_message
@observe(name="chat.turn")
async def on_message(message: cl.Message) -> None:
    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": message.content})

    os.environ.setdefault("FASTMCP_TELEMETRY_MODE", "native")

    tools = _llm_tools()
    response = await _generate(messages, tools)
    choice = response.choices[0].message

    while choice.tool_calls:
        messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in choice.tool_calls
                ],
            }
        )

        for tool_call in choice.tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")
            tool_result = await _dispatch_tool(tool_call.function.name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                }
            )

        response = await _generate(messages, tools)
        choice = response.choices[0].message

    assistant_text = choice.content or "I could not generate a response."
    messages.append({"role": "assistant", "content": assistant_text})
    cl.user_session.set("messages", messages)
    await cl.Message(content=assistant_text).send()

    if settings.langfuse_configured:
        from langfuse import get_client

        get_client().flush()
