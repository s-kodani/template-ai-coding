from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx2
from mcp import types
from mcp.client import advertise
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from opentelemetry import context as otel_context
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from mcp_gateway.errors import GatewayError

_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
_TRACE_PROPAGATOR = TraceContextTextMapPropagator()
_BAGGAGE_PROPAGATOR = W3CBaggagePropagator()
_UI_EXTENSION = advertise(
    "io.modelcontextprotocol/ui", {"mimeTypes": ["text/html;profile=mcp-app"]}
)


def attach_trace_from_headers(headers: dict[str, str]) -> object:
    carrier = {str(key).lower(): str(value) for key, value in headers.items()}
    ctx = _TRACE_PROPAGATOR.extract(carrier)
    ctx = _BAGGAGE_PROPAGATOR.extract(carrier, context=ctx)
    return otel_context.attach(ctx)


def detach_trace(token: object) -> None:
    otel_context.detach(token)


def _validate_registry_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise GatewayError(404, "MCP_SERVER_NOT_FOUND", "MCP server is not registered")
    hostname = (parsed.hostname or "").lower()
    if hostname in _BLOCKED_HOSTS:
        raise GatewayError(404, "MCP_SERVER_NOT_FOUND", "MCP server is not registered")


def _trace_meta() -> dict[str, str]:
    carrier: dict[str, str] = {}
    _TRACE_PROPAGATOR.inject(carrier)
    _BAGGAGE_PROPAGATOR.inject(carrier)
    return {
        key: value
        for key, value in carrier.items()
        if key in {"traceparent", "tracestate", "baggage"}
        and "token" not in key.lower()
    }


@asynccontextmanager
async def _client(url: str, token: str, timeout_seconds: float) -> AsyncIterator[Client]:
    _validate_registry_url(url)
    http_client = httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    try:
        # The public Gateway and FastMCP 3 use the 2025-11-25 handshake protocol.
        async with Client(
            streamable_http_client(url, http_client=http_client),
            mode="legacy",
            extensions=[_UI_EXTENSION],
            read_timeout_seconds=timeout_seconds,
        ) as client:
            yield client
    except (TimeoutError, httpx2.TimeoutException) as exc:
        raise GatewayError(504, "MCP_TIMEOUT", "MCP request timed out") from exc
    except GatewayError:
        raise
    except MCPError as exc:
        if exc.code == types.REQUEST_TIMEOUT:
            raise GatewayError(504, "MCP_TIMEOUT", "MCP request timed out") from exc
        raise GatewayError(502, "MCP_UPSTREAM_ERROR", "MCP server error") from exc
    except Exception as exc:
        raise GatewayError(502, "MCP_UPSTREAM_ERROR", "MCP server error") from exc
    finally:
        await http_client.aclose()


async def call_mcp_tool(
    *,
    url: str,
    token: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with _client(url, token, timeout_seconds) as client:
        result = await client.call_tool(
            tool_name, arguments, meta=meta or _trace_meta() or None
        )
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)


async def list_mcp_tools(
    *,
    url: str,
    token: str,
    timeout_seconds: float,
    cursor: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with _client(url, token, timeout_seconds) as client:
        result = await client.list_tools(cursor=cursor, meta=meta)
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)


async def list_mcp_resources(
    *,
    url: str,
    token: str,
    timeout_seconds: float,
    cursor: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with _client(url, token, timeout_seconds) as client:
        result = await client.list_resources(cursor=cursor, meta=meta)
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)


async def read_mcp_resource(
    *,
    url: str,
    token: str,
    uri: str,
    timeout_seconds: float,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with _client(url, token, timeout_seconds) as client:
        result = await client.read_resource(uri, meta=meta or _trace_meta() or None)
        return result.model_dump(mode="json", by_alias=True, exclude_none=True)
