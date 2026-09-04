from __future__ import annotations

import os
import sys
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any

from fastmcp.telemetry import get_tracer
from langfuse import Langfuse, get_client, propagate_attributes
from langfuse.span_filter import is_default_export_span
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_langfuse_client: Langfuse | None = None
_langfuse_enabled = False
_TRACE_OUTPUT_MAX_CONTENT_LENGTH = 500

ALLOWED_EXTRA_SCOPE_PREFIXES = frozenset(
    {
        "fastmcp",
        "opentelemetry.instrumentation.asyncpg",
    }
)
_TRACE_CONTEXT_PROPAGATOR = TraceContextTextMapPropagator()
_BAGGAGE_PROPAGATOR = W3CBaggagePropagator()
_META_PROPAGATION_KEYS = ("traceparent", "tracestate", "baggage")
_FASTMCP_PROPAGATION_ALIASES = (
    ("fastmcp.client.mixins.tools", "inject_trace_context", "inject"),
    ("fastmcp.server.telemetry", "extract_trace_context", "extract"),
)


def langfuse_tracing_enabled() -> bool:
    return _langfuse_enabled


def _matches_scope_prefix(scope_name: str, prefix: str) -> bool:
    return scope_name == prefix or scope_name.startswith(f"{prefix}.")


def should_export_langfuse_span(span: ReadableSpan) -> bool:
    """Export Langfuse defaults plus FastMCP and asyncpg client spans."""
    if is_default_export_span(span):
        return True
    if span.instrumentation_scope is None:
        return False
    name = span.instrumentation_scope.name
    return any(_matches_scope_prefix(name, prefix) for prefix in ALLOWED_EXTRA_SCOPE_PREFIXES)


def inject_langfuse_propagated_meta(meta: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Inject W3C trace context and baggage into MCP `_meta`."""
    carrier: dict[str, str] = {}
    _TRACE_CONTEXT_PROPAGATOR.inject(carrier)
    _BAGGAGE_PROPAGATOR.inject(carrier)
    propagated = {key: carrier[key] for key in _META_PROPAGATION_KEYS if key in carrier}
    if not propagated:
        return meta
    return {**(meta or {}), **propagated}


def extract_langfuse_propagated_context(meta: dict[str, Any] | None) -> Context:
    """Restore W3C trace context and baggage from MCP `_meta`."""
    current_span = trace.get_current_span()
    if current_span.get_span_context().is_valid:
        return otel_context.get_current()
    if not meta:
        return otel_context.get_current()

    carrier = {key: str(meta[key]) for key in _META_PROPAGATION_KEYS if key in meta}
    if not carrier:
        return otel_context.get_current()

    context = _TRACE_CONTEXT_PROPAGATOR.extract(carrier)
    return _BAGGAGE_PROPAGATOR.extract(carrier, context=context)


def _install_fastmcp_baggage_propagation() -> None:
    """Replace FastMCP inject/extract so Langfuse baggage crosses MCP `_meta`."""
    from fastmcp import telemetry

    telemetry.inject_trace_context = inject_langfuse_propagated_meta
    telemetry.extract_trace_context = extract_langfuse_propagated_context

    replacements = {
        "inject": inject_langfuse_propagated_meta,
        "extract": extract_langfuse_propagated_context,
    }
    for module_name, attr, kind in _FASTMCP_PROPAGATION_ALIASES:
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, attr):
            setattr(module, attr, replacements[kind])


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def configure_langfuse_tracing() -> Langfuse | None:
    """Initialize Langfuse OTel export before FastMCP is imported."""
    global _langfuse_client, _langfuse_enabled

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    enabled = os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() == "true"

    if not enabled or not public_key or not secret_key:
        _langfuse_client = None
        _langfuse_enabled = False
        return None

    _langfuse_client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host.rstrip("/"),
        environment=_optional_env("LANGFUSE_TRACING_ENVIRONMENT"),
        release=_optional_env("LANGFUSE_RELEASE"),
        should_export_span=should_export_langfuse_span,
    )
    _langfuse_enabled = True
    _install_fastmcp_baggage_propagation()
    return _langfuse_client


def flush_langfuse() -> None:
    if not _langfuse_enabled:
        return
    try:
        get_client().flush()
    except (ImportError, RuntimeError, AttributeError):
        if _langfuse_client is not None:
            _langfuse_client.flush()


def chat_trace_attributes(
    *,
    user_id: str | None,
    session_id: str | None,
    chat_model: str,
    tags: list[str] | None = None,
) -> AbstractContextManager[Any]:
    """Propagate trace-level attributes for a Chainlit turn (with MCP baggage)."""
    if not _langfuse_enabled:
        return nullcontext()

    metadata: dict[str, str] = {
        "component": "chainlit",
        "chat_model": chat_model,
    }
    return propagate_attributes(
        user_id=user_id,
        session_id=session_id,
        tags=tags or ["chainlit"],
        metadata=metadata,
        as_baggage=True,
    )


@contextmanager
def tool_observation(
    name: str,
    arguments: dict[str, Any],
    *,
    metadata: dict[str, str] | None = None,
) -> AbstractContextManager[Any]:
    """Record MCP tool input as a nested Langfuse tool observation."""
    if not _langfuse_enabled:
        with nullcontext() as observation:
            yield observation
        return

    client = get_client()
    with client.start_as_current_observation(
        as_type="tool",
        name=name,
        input=arguments,
        metadata=metadata or {},
    ) as observation:
        yield observation


@contextmanager
def embedding_observation(
    *,
    model: str,
    input_length: int,
    dimensions: int,
) -> AbstractContextManager[Any]:
    """Record embedding API call as a Langfuse embedding observation."""
    if not _langfuse_enabled:
        with nullcontext() as observation:
            yield observation
        return

    client = get_client()
    with client.start_as_current_observation(
        as_type="embedding",
        name="search.embed",
        model=model,
        input={"input_length": input_length, "dimensions": dimensions},
    ) as observation:
        yield observation


def record_embedding_usage(observation: Any, usage: dict[str, int] | None) -> None:
    if observation is None or not usage:
        return
    try:
        observation.update(usage_details=usage)
    except (AttributeError, TypeError, ValueError):
        return


def record_generation_result(response: Any, *, model: str) -> None:
    """Attach model and token usage to the active Langfuse generation observation."""
    if not _langfuse_enabled:
        return
    try:
        client = get_client()
        usage = getattr(response, "usage", None)
        usage_details: dict[str, int] | None = None
        if usage is not None:
            usage_details = {}
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if prompt_tokens is not None:
                usage_details["input"] = int(prompt_tokens)
            if completion_tokens is not None:
                usage_details["output"] = int(completion_tokens)
            if total_tokens is not None:
                usage_details["total"] = int(total_tokens)
            if not usage_details:
                usage_details = None
        client.update_current_generation(
            model=model,
            usage_details=usage_details,
            metadata={"tool_choice": "auto"},
        )
    except (ImportError, RuntimeError, AttributeError):
        return


def update_current_turn_io(*, user_message: str, assistant_message: str | None = None) -> None:
    """Set chat.turn input and optional final assistant output."""
    if not _langfuse_enabled:
        return
    try:
        client = get_client()
        client.update_current_span(input={"content": user_message})
        if assistant_message is not None:
            client.update_current_span(output={"content": assistant_message})
    except (ImportError, RuntimeError, AttributeError):
        return


def sanitize_tool_output_for_trace(output: dict[str, Any]) -> dict[str, Any]:
    """Redact large document bodies before exporting tool output to Langfuse."""
    content = output.get("content")
    if not isinstance(content, str) or len(content) <= _TRACE_OUTPUT_MAX_CONTENT_LENGTH:
        return output

    truncated = content[:_TRACE_OUTPUT_MAX_CONTENT_LENGTH].rstrip() + "…"
    return {**output, "content": truncated}


def record_tool_input(arguments: dict[str, Any]) -> None:
    """Attach tool input to the active FastMCP server span (propagated trace)."""
    if not _langfuse_enabled:
        return
    try:
        get_client().update_current_span(input=arguments)
    except (ImportError, RuntimeError, AttributeError):
        return


def record_tool_output(output: dict[str, Any]) -> None:
    """Attach sanitized tool output to the active span (FastMCP server or Langfuse observation)."""
    if not _langfuse_enabled:
        return
    try:
        get_client().update_current_span(
            output=sanitize_tool_output_for_trace(output),
        )
    except (ImportError, RuntimeError, AttributeError):
        return


@contextmanager
def search_span(name: str) -> AbstractContextManager[Any]:
    """OTel span nested under the current trace context (e.g. FastMCP server span)."""
    with get_tracer().start_as_current_span(name) as span:
        yield span


def instrument_asyncpg() -> None:
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
    except ImportError:
        return
