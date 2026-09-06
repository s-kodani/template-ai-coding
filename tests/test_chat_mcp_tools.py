from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from chat_ui.mcp_tools import (
    call_session_tool,
    catalog_from_listed_tools,
    collect_openai_tools,
    find_session_for_tool,
    llm_tool_name,
    mcp_tool_name_from_llm,
    openai_tool_from_mcp,
    parse_tool_result,
    prefix_tools_for_gateway,
    resolve_tool_target,
)

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge",
        "description": "Search the local knowledge base.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
}


def test_openai_tool_from_mcp_maps_schema() -> None:
    tool = openai_tool_from_mcp(
        {
            "name": "list_buckets",
            "description": "List S3 buckets",
            "inputSchema": {
                "type": "object",
                "properties": {"prefix": {"type": "string"}},
                "required": ["prefix"],
            },
        }
    )

    assert tool == {
        "type": "function",
        "function": {
            "name": "list_buckets",
            "description": "List S3 buckets",
            "parameters": {
                "type": "object",
                "properties": {"prefix": {"type": "string"}},
                "required": ["prefix"],
            },
        },
    }


def test_openai_tool_from_mcp_defaults_empty_schema() -> None:
    tool = openai_tool_from_mcp({"name": "ping", "description": None})

    assert tool["function"]["name"] == "ping"
    assert tool["function"]["description"] == ""
    assert tool["function"]["parameters"] == {"type": "object", "properties": {}}


def test_collect_openai_tools_keeps_defaults_and_appends_unique() -> None:
    session_tools = {
        "aws": [
            {
                "name": "list_buckets",
                "description": "List S3 buckets",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
    }

    tools = collect_openai_tools([SEARCH_TOOL], session_tools)

    names = [t["function"]["name"] for t in tools]
    assert names == ["search_knowledge", "list_buckets"]


def test_collect_openai_tools_skips_default_name_collision() -> None:
    session_tools = {
        "other": [
            {
                "name": "search_knowledge",
                "description": "Duplicate",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]
    }

    tools = collect_openai_tools([SEARCH_TOOL], session_tools)

    names = [t["function"]["name"] for t in tools]
    assert names == ["search_knowledge"]
    assert tools[0]["function"]["description"] == "Search the local knowledge base."


def test_collect_openai_tools_first_session_wins_on_collision() -> None:
    session_tools = {
        "first": [
            {
                "name": "echo",
                "description": "from first",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
        "second": [
            {
                "name": "echo",
                "description": "from second",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ],
    }

    tools = collect_openai_tools([], session_tools)

    assert len(tools) == 1
    assert tools[0]["function"]["description"] == "from first"


def test_find_session_for_tool_returns_owning_connection() -> None:
    session_tools = {
        "aws": [{"name": "list_buckets"}],
        "docs": [{"name": "search_docs"}],
    }

    assert find_session_for_tool("search_docs", session_tools) == "docs"
    assert find_session_for_tool("missing", session_tools) is None


def test_resolve_tool_target_uses_session_tools_only() -> None:
    session_tools = {
        "knowledge-mcp": [{"name": "knowledge__search_knowledge"}, {"name": "list_buckets"}]
    }

    assert resolve_tool_target("knowledge__search_knowledge", session_tools) == (
        "session",
        "knowledge-mcp",
    )
    assert resolve_tool_target("list_buckets", session_tools) == ("session", "knowledge-mcp")
    assert resolve_tool_target("unknown", session_tools) == ("unknown", None)


def test_llm_and_mcp_tool_name_roundtrip() -> None:
    llm_name = llm_tool_name("knowledge", "search_knowledge")
    assert llm_name == "knowledge__search_knowledge"
    assert mcp_tool_name_from_llm(llm_name, "knowledge") == "search_knowledge"


def test_prefix_tools_for_gateway() -> None:
    prefixed = prefix_tools_for_gateway(
        "knowledge",
        [{"name": "search_knowledge", "description": "Search", "inputSchema": {}}],
    )
    assert prefixed == [
        {
            "name": "knowledge__search_knowledge",
            "description": "Search",
            "inputSchema": {},
        }
    ]


def test_catalog_from_listed_tools_prefixes_server_id_and_keeps_collisions() -> None:
    tools, targets = catalog_from_listed_tools(
        [
            (
                "knowledge",
                [{"name": "search_knowledge", "description": "kb", "inputSchema": {}}],
            ),
            (
                "other",
                [
                    {"name": "search_knowledge", "description": "dup", "inputSchema": {}},
                    {"name": "ping", "description": "p", "inputSchema": {}},
                ],
            ),
        ]
    )
    assert [tool["function"]["name"] for tool in tools] == [
        "knowledge__search_knowledge",
        "other__search_knowledge",
        "other__ping",
    ]
    assert tools[0]["function"]["description"] == "kb"
    assert tools[1]["function"]["description"] == "dup"
    assert targets == {
        "knowledge__search_knowledge": ("knowledge", "search_knowledge"),
        "other__search_knowledge": ("other", "search_knowledge"),
        "other__ping": ("other", "ping"),
    }


def test_parse_tool_result_json_text() -> None:
    result = SimpleNamespace(
        isError=False,
        content=[SimpleNamespace(text='{"hits": []}')],
    )

    assert parse_tool_result(result) == {"hits": []}


def test_parse_tool_result_non_json_text() -> None:
    result = SimpleNamespace(isError=False, content=[SimpleNamespace(text="plain")])

    assert parse_tool_result(result) == {"text": "plain"}


def test_parse_tool_result_empty_content() -> None:
    result = SimpleNamespace(isError=False, content=[])

    assert parse_tool_result(result) == {"error": "Tool returned no content."}


def test_parse_tool_result_error_flag() -> None:
    result = SimpleNamespace(isError=True, content=[SimpleNamespace(text="boom")])

    assert parse_tool_result(result) == {"error": "boom"}


def test_parse_tool_result_snake_case_error_flag() -> None:
    result = SimpleNamespace(is_error=True, content=[SimpleNamespace(text="boom")])

    assert parse_tool_result(result) == {"error": "boom"}


@pytest.mark.asyncio
async def test_call_session_tool_injects_traceparent(span_exporter) -> None:
    session = SimpleNamespace()
    session.call_tool = AsyncMock(
        return_value=SimpleNamespace(
            isError=False,
            content=[SimpleNamespace(text='{"ok": true}')],
        )
    )

    from opentelemetry import trace

    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("chat.turn"):
        payload = await call_session_tool(session, "list_buckets", {"prefix": "a"})

    assert payload == {"ok": True}
    session.call_tool.assert_awaited_once()
    _, kwargs = session.call_tool.await_args
    meta = kwargs["meta"]
    assert meta is not None
    assert "traceparent" in meta
