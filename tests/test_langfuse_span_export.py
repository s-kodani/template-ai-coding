from __future__ import annotations

from types import SimpleNamespace

from langfuse._client.propagation import (
    _get_langfuse_trace_id_from_baggage,
    _set_langfuse_trace_id_in_baggage,
)
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import format_trace_id

from knowledge_mcp.tracing import (
    extract_langfuse_propagated_context,
    inject_langfuse_propagated_meta,
    should_export_langfuse_span,
)


def _span(scope_name: str | None, attributes: dict | None = None) -> SimpleNamespace:
    scope = None if scope_name is None else SimpleNamespace(name=scope_name)
    return SimpleNamespace(instrumentation_scope=scope, attributes=attributes)


def test_export_keeps_langfuse_sdk_spans() -> None:
    assert should_export_langfuse_span(_span("langfuse-sdk")) is True


def test_export_keeps_openai_instrumentor_spans() -> None:
    assert should_export_langfuse_span(_span("opentelemetry.instrumentation.openai")) is True


def test_export_keeps_fastmcp_spans() -> None:
    assert should_export_langfuse_span(_span("fastmcp")) is True


def test_export_keeps_asyncpg_instrumentor_spans() -> None:
    assert should_export_langfuse_span(_span("opentelemetry.instrumentation.asyncpg")) is True


def test_export_drops_unrelated_http_client_spans() -> None:
    assert should_export_langfuse_span(_span("opentelemetry.instrumentation.httpx")) is False
    assert should_export_langfuse_span(_span("opentelemetry.instrumentation.requests")) is False


def test_configure_langfuse_tracing_passes_export_filter(monkeypatch) -> None:
    from knowledge_mcp import tracing

    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")

    captured: dict = {}

    def fake_langfuse(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(tracing, "Langfuse", fake_langfuse)
    tracing._langfuse_client = None
    tracing._langfuse_enabled = False

    import fastmcp.client.mixins.tools as client_tools
    from fastmcp import telemetry

    try:
        client = tracing.configure_langfuse_tracing()
        assert client is not None
        assert captured["should_export_span"] is tracing.should_export_langfuse_span
        assert telemetry.inject_trace_context is tracing.inject_langfuse_propagated_meta
        assert telemetry.extract_trace_context is tracing.extract_langfuse_propagated_context
        assert client_tools.inject_trace_context is tracing.inject_langfuse_propagated_meta
    finally:
        tracing._langfuse_client = None
        tracing._langfuse_enabled = False


def test_inject_meta_includes_langfuse_trace_id_baggage(
    span_exporter,
) -> None:
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("chat.turn") as span:
        trace_id = format_trace_id(span.get_span_context().trace_id)
        token = otel_context.attach(
            _set_langfuse_trace_id_in_baggage(
                trace_id=trace_id,
                context=otel_context.get_current(),
            )
        )
        try:
            meta = inject_langfuse_propagated_meta({})
        finally:
            otel_context.detach(token)

    assert meta is not None
    assert "traceparent" in meta
    assert "langfuse_trace_id" in str(meta.get("baggage", ""))


def test_extract_meta_restores_langfuse_trace_id_in_isolated_context(
    span_exporter,
) -> None:
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("chat.turn") as span:
        trace_id = format_trace_id(span.get_span_context().trace_id)
        token = otel_context.attach(
            _set_langfuse_trace_id_in_baggage(
                trace_id=trace_id,
                context=otel_context.get_current(),
            )
        )
        try:
            meta = inject_langfuse_propagated_meta({})
        finally:
            otel_context.detach(token)

    empty = otel_context.Context()
    token = otel_context.attach(empty)
    try:
        restored = extract_langfuse_propagated_context(meta)
        assert _get_langfuse_trace_id_from_baggage(restored) == trace_id
    finally:
        otel_context.detach(token)
