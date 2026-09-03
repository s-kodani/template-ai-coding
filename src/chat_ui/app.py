from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import chainlit as cl
from chainlit.server import app as chainlit_app
from langfuse import observe

from chat_ui.auth import register_oauth_callback, set_token_manager
from chat_ui.gateway_client import MCPGatewayClient, call_gateway_tool, load_gateway_catalog
from chat_ui.gateway_registry import load_ui_servers
from chat_ui.gateway_routes import register_gateway_mcp_routes
from chat_ui.mcp_bridge import build_openai_client
from chat_ui.mcp_tools import (
    call_session_tool,
    collect_openai_tools,
    filter_gateway_catalog,
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
_ui_servers = load_ui_servers(Path(settings.mcp_gateway_registry_path))
_ui_name_to_id = {str(entry["name"]): str(entry["id"]) for entry in _ui_servers}
write_mcp_autoload_script(Path.cwd() / "public", _ui_servers)
register_oauth_callback()
register_gateway_mcp_routes(chainlit_app, name_to_id=_ui_name_to_id)

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to MCP tools from the gateway "
    "and any additional MCP servers the user has connected. "
    "Use those tools when they help answer the user."
)


def _session_user() -> Any:
    return cl.user_session.get("user") or getattr(cl.context.session, "user", None)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("messages", [{"role": "system", "content": SYSTEM_PROMPT}])
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("gateway_tools", [])
    cl.user_session.set("gateway_targets", {})
    user = _session_user()
    subject = (getattr(user, "metadata", None) or {}).get("keycloak_sub")
    if subject:
        await token_manager.bind_session(str(subject), cl.context.session.id)
        token = await token_manager.get_access_token(cl.context.session.id)
        if token:
            tools, targets = await load_gateway_catalog(gateway_client, token)
            cl.user_session.set("gateway_catalog_tools", tools)
            cl.user_session.set("gateway_catalog_targets", targets)
            disabled = set(cl.user_session.get("gateway_disabled") or set())
            enabled = {ref[0] for ref in targets.values()} - disabled
            filtered_tools, filtered_targets = filter_gateway_catalog(
                tools, targets, enabled
            )
            cl.user_session.set("gateway_tools", filtered_tools)
            cl.user_session.set("gateway_targets", filtered_targets)
            cl.user_session.set("gateway_enabled", enabled)
            cl.user_session.set("gateway_disabled", disabled)


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
        cl.user_session.get("gateway_tools") or [],
        cl.user_session.get("mcp_tools") or {},
    )


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    session_tools = cl.user_session.get("mcp_tools") or {}
    targets = cl.user_session.get("gateway_targets") or {}
    kind, target = resolve_tool_target(name, session_tools, targets)
    tool_metadata: dict[str, str] = {"tool.route": kind, "tool.llm_name": name}
    if kind == "gateway" and target:
        mapped = targets.get(name)
        mcp_name = mapped[1] if isinstance(mapped, tuple) else name
        tool_metadata["tool.server_id"] = target
        tool_metadata["tool.mcp_name"] = mcp_name
        return await call_gateway_tool(
            gateway_client,
            token_manager,
            cl.context.session.id,
            mcp_name,
            arguments,
            server_id=target,
            tool_metadata=tool_metadata,
        )
    if kind == "session" and target:
        tool_metadata["tool.session"] = target
        tool_metadata["tool.mcp_name"] = name
        entry = cl.context.session.mcp_sessions.get(target)
        if not entry:
            return {"error": f"MCP session not found: {target}"}
        mcp_session, _ = entry
        return await call_session_tool(mcp_session, name, arguments, tool_metadata=tool_metadata)
    return {"error": f"Unknown tool: {name}"}


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
