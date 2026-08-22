from __future__ import annotations

import json
import os
from typing import Any

import chainlit as cl
from langfuse import observe

from chat_ui.mcp_bridge import GET_DOCUMENT_TOOL, SEARCH_TOOL, MCPBridge, build_openai_client
from knowledge_mcp.config import get_settings
from knowledge_mcp.tracing import configure_langfuse_tracing, instrument_asyncpg

_langfuse = configure_langfuse_tracing()
instrument_asyncpg()

settings = get_settings()
openai_client = build_openai_client(settings)
mcp_bridge = MCPBridge(settings)

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a local knowledge base. "
    "Use search_knowledge when the user asks about project documentation. "
    "Cite document titles and ids from tool results."
)


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("messages", [{"role": "system", "content": SYSTEM_PROMPT}])


async def _dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "search_knowledge":
        return await mcp_bridge.call_tool("search_knowledge", arguments)
    if name == "get_document":
        return await mcp_bridge.call_tool("get_document", arguments)
    return {"error": f"Unknown tool: {name}"}


@observe(name="llm.generate")
async def _generate(messages: list[dict[str, Any]]) -> Any:
    return await openai_client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        tools=[SEARCH_TOOL, GET_DOCUMENT_TOOL],
        tool_choice="auto",
    )


@cl.on_message
@observe(name="chat.turn")
async def on_message(message: cl.Message) -> None:
    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": message.content})

    os.environ.setdefault("FASTMCP_TELEMETRY_MODE", "native")

    response = await _generate(messages)
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

        response = await _generate(messages)
        choice = response.choices[0].message

    assistant_text = choice.content or "I could not generate a response."
    messages.append({"role": "assistant", "content": assistant_text})
    cl.user_session.set("messages", messages)
    await cl.Message(content=assistant_text).send()

    if settings.langfuse_configured:
        from langfuse import get_client

        get_client().flush()
