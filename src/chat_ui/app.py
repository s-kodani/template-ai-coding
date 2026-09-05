from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import chainlit as cl
from chainlit.server import app as chainlit_app
from langfuse import observe

from chat_ui.auth import register_oauth_callback, set_token_manager
from chat_ui.gateway_client import MCPGatewayClient, _http_status
from chat_ui.gateway_mcp_connect import (
    auto_connect_gateway_mcps,
    reconnect_gateway_mcp,
    register_gateway_mcp_connect,
)
from chat_ui.gateway_registry import load_id_to_name, load_name_index, load_ui_servers
from chat_ui.mcp_bridge import build_openai_client
from chat_ui.mcp_tools import (
    call_session_tool,
    collect_openai_tools,
    mcp_tool_name_from_llm,
    prefix_tools_for_gateway,
    resolve_tool_target,
)
from chat_ui.mcp_ui import write_mcp_autoload_script
from chat_ui.token_manager import build_token_manager
from knowledge_mcp.config import get_settings
from knowledge_mcp.tracing import (
    chat_trace_attributes,
    configure_langfuse_tracing,
    flush_langfuse,
    instrument_asyncpg,
    record_generation_result,
    update_current_turn_io,
)

_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

settings = get_settings()
openai_client = build_openai_client(settings)
gateway_client = MCPGatewayClient(settings.mcp_gateway_url)
token_manager = build_token_manager(settings)
set_token_manager(token_manager)
_registry_path = Path(settings.mcp_gateway_registry_path)
_ui_servers = load_ui_servers(_registry_path)
_ui_name_to_id = load_name_index(_registry_path)
_ui_id_to_name = load_id_to_name(_registry_path)
write_mcp_autoload_script(Path.cwd() / "public", _ui_servers)
register_oauth_callback()
register_gateway_mcp_connect(
    chainlit_app,
    name_to_id=_ui_name_to_id,
    token_manager=token_manager,
    gateway_client=gateway_client,
)

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to MCP tools from the gateway "
    "and any additional MCP servers the user has connected. "
    "Use those tools when they help answer the user."
)


def _session_user() -> Any:
    return cl.user_session.get("user") or getattr(cl.context.session, "user", None)


def _gateway_server_for_connection(connection_name: str) -> str | None:
    mapping = cl.user_session.get("gateway_server_by_connection") or {}
    return mapping.get(connection_name)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("messages", [{"role": "system", "content": SYSTEM_PROMPT}])
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("gateway_server_by_connection", {})
    user = _session_user()
    subject = (getattr(user, "metadata", None) or {}).get("keycloak_sub")
    if subject:
        await token_manager.bind_session(str(subject), cl.context.session.id)
        await auto_connect_gateway_mcps(
            cl.context.session,
            name_to_id=_ui_name_to_id,
            id_to_name=_ui_id_to_name,
            token_manager=token_manager,
            gateway_client=gateway_client,
        )


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
    server_id = _ui_name_to_id.get(connection.name)
    if server_id:
        tools = prefix_tools_for_gateway(server_id, tools)
        mapping = cl.user_session.get("gateway_server_by_connection") or {}
        mapping[connection.name] = server_id
        cl.user_session.set("gateway_server_by_connection", mapping)
    mcp_tools = cl.user_session.get("mcp_tools") or {}
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)


@cl.on_mcp_disconnect
async def on_mcp_disconnect(name: str, _session: Any) -> None:
    mcp_tools = cl.user_session.get("mcp_tools") or {}
    mcp_tools.pop(name, None)
    cl.user_session.set("mcp_tools", mcp_tools)
    mapping = cl.user_session.get("gateway_server_by_connection") or {}
    if name in mapping:
        mapping.pop(name, None)
        cl.user_session.set("gateway_server_by_connection", mapping)


def _llm_tools() -> list[dict[str, Any]]:
    return collect_openai_tools([], cl.user_session.get("mcp_tools") or {})


def _is_token_expired(result: dict[str, Any]) -> bool:
    return result.get("error") == "TOKEN_EXPIRED" or result.get("status_code") == 401


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    session_tools = cl.user_session.get("mcp_tools") or {}
    kind, target = resolve_tool_target(name, session_tools)
    tool_metadata: dict[str, str] = {"tool.route": kind, "tool.llm_name": name}
    if kind != "session" or not target:
        return {"error": f"Unknown tool: {name}"}

    server_id = _gateway_server_for_connection(target)
    mcp_name = mcp_tool_name_from_llm(name, server_id) if server_id else name
    tool_metadata["tool.session"] = target
    tool_metadata["tool.mcp_name"] = mcp_name
    if server_id:
        tool_metadata["tool.server_id"] = server_id

    entry = cl.context.session.mcp_sessions.get(target)
    if not entry:
        return {"error": f"MCP session not found: {target}"}
    mcp_session, _ = entry

    try:
        result = await call_session_tool(
            mcp_session, mcp_name, arguments, tool_metadata=tool_metadata
        )
    except Exception as exc:  # noqa: BLE001 - map MCP transport failures to tool output
        if _http_status(exc) == 401:
            result = {"error": "TOKEN_EXPIRED", "status_code": 401}
        else:
            return {"error": str(exc) or "Tool call failed"}

    if server_id and _is_token_expired(result):
        await reconnect_gateway_mcp(
            cl.context.session,
            target,
            name_to_id=_ui_name_to_id,
            token_manager=token_manager,
            gateway_client=gateway_client,
        )
        entry = cl.context.session.mcp_sessions.get(target)
        if not entry:
            return result
        mcp_session, _ = entry
        result = await call_session_tool(
            mcp_session, mcp_name, arguments, tool_metadata=tool_metadata
        )
    return result


@observe(name="llm.generate", as_type="generation", capture_input=False, capture_output=False)
async def _generate(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
    response = await openai_client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )
    record_generation_result(response, model=settings.chat_model)
    return response


@cl.on_message
@observe(name="chat.turn", capture_input=False, capture_output=False)
async def on_message(message: cl.Message) -> None:
    user = _session_user()
    user_metadata = getattr(user, "metadata", None) or {}
    user_id = str(user_metadata.get("keycloak_sub") or getattr(user, "identifier", "") or "") or None
    session_id = str(cl.context.session.id)

    with chat_trace_attributes(
        user_id=user_id,
        session_id=session_id,
        chat_model=settings.chat_model,
    ):
        update_current_turn_io(user_message=message.content)

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
        update_current_turn_io(user_message=message.content, assistant_message=assistant_text)
        await cl.Message(content=assistant_text).send()

        if settings.langfuse_configured:
            flush_langfuse()
