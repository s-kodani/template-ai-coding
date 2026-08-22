from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client
from fastmcp.telemetry import extract_trace_context, inject_trace_context
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@contextmanager
def detached_context():
    token = otel_context.attach(otel_context.Context())
    try:
        yield
    finally:
        otel_context.detach(token)


def _span_by_name(spans: list, name: str, kind: str | None = None):
    matches = [span for span in spans if span.name == name or span.name.startswith(name)]
    if kind is not None:
        matches = [span for span in matches if span.kind.name == kind]
    if len(matches) != 1:
        names = [(span.name, span.kind.name) for span in spans]
        raise AssertionError(f"Expected one span matching {name!r}, got {names}")
    return matches[0]


@pytest.mark.asyncio
async def test_fastmcp_client_span_is_child_of_root(span_exporter: InMemorySpanExporter) -> None:
    from knowledge_mcp import server
    from knowledge_mcp.models import SearchResult

    fake_result = SearchResult(query="tracing", hits=[])
    with patch.object(server.repository, "connect", AsyncMock()), patch.object(
        server.repository, "close", AsyncMock()
    ), patch.object(server.embedding_client, "aclose", AsyncMock()), patch.object(
        server.search_service, "search_knowledge", AsyncMock(return_value=fake_result)
    ):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("chat.turn") as root:
            root_id = root.get_span_context().span_id

            async with Client(server.mcp) as client:
                await client.call_tool("search_knowledge", {"query": "tracing", "top_k": 3})

    spans = span_exporter.get_finished_spans()
    client_span = _span_by_name(spans, "tools/call search_knowledge", kind="CLIENT")

    assert client_span.context.trace_id == root.get_span_context().trace_id
    assert client_span.parent.span_id == root_id


def test_meta_traceparent_links_server_span_when_context_isolated(
    span_exporter: InMemorySpanExporter,
) -> None:
    tracer = trace.get_tracer("test")

    with (
        tracer.start_as_current_span("chat.turn"),
        tracer.start_as_current_span("tools/call search_knowledge") as client_span,
    ):
        meta = inject_trace_context({})
        client_span_id = client_span.get_span_context().span_id

    assert meta is not None
    assert "traceparent" in meta

    with detached_context():
        server_context = extract_trace_context(meta)
        with tracer.start_as_current_span(
            "tools/call search_knowledge",
            context=server_context,
            kind=trace.SpanKind.SERVER,
        ) as server_span:
            assert server_span.parent.span_id == client_span_id


@pytest.mark.asyncio
async def test_search_spans_nest_under_server_span(span_exporter: InMemorySpanExporter) -> None:
    from knowledge_mcp import server
    from knowledge_mcp.models import SearchHit

    hits = [
        SearchHit(
            document_id="doc-1",
            title="Tracing",
            excerpt="Trace context propagates",
            source="fixture",
            similarity=0.91,
        )
    ]
    with patch.object(server.repository, "connect", AsyncMock()), patch.object(
        server.repository, "close", AsyncMock()
    ), patch.object(server.embedding_client, "aclose", AsyncMock()), patch.object(
        server.embedding_client, "embed", AsyncMock(return_value=[0.1] * 1536)
    ), patch.object(server.repository, "search", AsyncMock(return_value=hits)):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("chat.turn"):
            async with Client(server.mcp) as client:
                await client.call_tool("search_knowledge", {"query": "tracing", "top_k": 3})

    spans = span_exporter.get_finished_spans()
    server_span = _span_by_name(spans, "tools/call search_knowledge", kind="SERVER")
    embed_span = _span_by_name(spans, "search.embed")
    query_span = _span_by_name(spans, "search.query")

    server_id = server_span.get_span_context().span_id
    assert embed_span.parent.span_id == server_id
    assert query_span.parent.span_id == server_id


@pytest.mark.asyncio
async def test_tool_call_spans_share_single_trace_id(span_exporter: InMemorySpanExporter) -> None:
    from knowledge_mcp import server
    from knowledge_mcp.models import SearchHit

    hits = [
        SearchHit(
            document_id="doc-1",
            title="Tracing",
            excerpt="Trace context propagates",
            source="fixture",
            similarity=0.91,
        )
    ]
    with patch.object(server.repository, "connect", AsyncMock()), patch.object(
        server.repository, "close", AsyncMock()
    ), patch.object(server.embedding_client, "aclose", AsyncMock()), patch.object(
        server.embedding_client, "embed", AsyncMock(return_value=[0.1] * 1536)
    ), patch.object(server.repository, "search", AsyncMock(return_value=hits)):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("chat.turn") as root:
            root_trace_id = root.get_span_context().trace_id
            async with Client(server.mcp) as client:
                await client.call_tool("search_knowledge", {"query": "architecture", "top_k": 5})

    spans = span_exporter.get_finished_spans()
    relevant = [
        span
        for span in spans
        if span.name
        in {
            "chat.turn",
            "search.embed",
            "search.query",
        }
        or span.name.startswith("tools/call search_knowledge")
    ]

    assert relevant
    assert {span.context.trace_id for span in relevant} == {root_trace_id}


@pytest.mark.asyncio
async def test_mcp_bridge_call_tool_preserves_root_trace(span_exporter: InMemorySpanExporter) -> None:
    from knowledge_mcp import server
    from knowledge_mcp.config import Settings
    from knowledge_mcp.models import SearchHit

    hits = [
        SearchHit(
            document_id="doc-1",
            title="Architecture",
            excerpt="System design",
            source="fixture",
            similarity=0.88,
        )
    ]
    with patch.object(server.repository, "connect", AsyncMock()), patch.object(
        server.repository, "close", AsyncMock()
    ), patch.object(server.embedding_client, "aclose", AsyncMock()), patch.object(
        server.embedding_client, "embed", AsyncMock(return_value=[0.1] * 1536)
    ), patch.object(server.repository, "search", AsyncMock(return_value=hits)):
        settings = Settings()
        from chat_ui.mcp_bridge import MCPBridge

        bridge = MCPBridge(settings)
        bridge._client = Client(server.mcp)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("chat.turn") as root:
            root_trace_id = root.get_span_context().trace_id
            await bridge.call_tool("search_knowledge", {"query": "architecture", "top_k": 5})

    spans = span_exporter.get_finished_spans()
    client_span = _span_by_name(spans, "tools/call search_knowledge", kind="CLIENT")
    server_span = _span_by_name(spans, "tools/call search_knowledge", kind="SERVER")

    assert client_span.context.trace_id == root_trace_id
    assert server_span.context.trace_id == root_trace_id
    assert client_span.parent.span_id == root.get_span_context().span_id
