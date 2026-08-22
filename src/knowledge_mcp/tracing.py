from __future__ import annotations

import os
from contextlib import AbstractContextManager, contextmanager, nullcontext
from typing import Any

from fastmcp.telemetry import get_tracer
from langfuse import Langfuse, get_client

_langfuse_client: Langfuse | None = None
_langfuse_enabled = False


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
    )
    _langfuse_enabled = True
    return _langfuse_client


def flush_langfuse() -> None:
    if not _langfuse_enabled:
        return
    try:
        get_client().flush()
    except (ImportError, RuntimeError, AttributeError):
        if _langfuse_client is not None:
            _langfuse_client.flush()


@contextmanager
def tool_observation(name: str, arguments: dict[str, Any]) -> AbstractContextManager[Any]:
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
    ) as observation:
        yield observation


def record_tool_input(arguments: dict[str, Any]) -> None:
    """Attach tool input to the active FastMCP server span (propagated trace)."""
    if not _langfuse_enabled:
        return
    try:
        get_client().update_current_span(input=arguments)
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
