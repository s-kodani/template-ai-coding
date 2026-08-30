from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx2
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client
from opentelemetry import context as otel_context
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from mcp_gateway.errors import GatewayError

_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}
_TRACE_PROPAGATOR = TraceContextTextMapPropagator()
_BAGGAGE_PROPAGATOR = W3CBaggagePropagator()


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


def _parse_tool_result(result: Any) -> dict[str, Any]:
    content = getattr(result, "content", None) or []
    if getattr(result, "is_error", False) or getattr(result, "isError", False):
        text = ""
        if content:
            first = content[0]
            text = getattr(first, "text", None) or str(first)
        return {"error": text or "Tool returned an error."}
    if not content:
        return {"error": "Tool returned no content."}
    first = content[0]
    text = getattr(first, "text", None) or str(first)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"text": text}


async def call_mcp_tool(
    *,
    url: str,
    token: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    _validate_registry_url(url)
    http_client = httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    try:
        async with Client(
            streamable_http_client(url, http_client=http_client),
            mode="auto",
            read_timeout_seconds=timeout_seconds,
        ) as client:
            result = await client.call_tool(tool_name, arguments, meta=_trace_meta() or None)
    except TimeoutError as exc:
        raise GatewayError(504, "MCP_TIMEOUT", "MCP tool call timed out") from exc
    except GatewayError:
        raise
    except Exception as exc:
        raise GatewayError(502, "MCP_UPSTREAM_ERROR", "MCP server error") from exc
    finally:
        await http_client.aclose()
    return _parse_tool_result(result)


async def list_mcp_tools(*, url: str, token: str, timeout_seconds: float) -> list[dict[str, Any]]:
    _validate_registry_url(url)
    http_client = httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    try:
        async with Client(
            streamable_http_client(url, http_client=http_client),
            mode="auto",
            read_timeout_seconds=timeout_seconds,
        ) as client:
            listed = await client.list_tools()
    except Exception as exc:
        raise GatewayError(502, "MCP_UPSTREAM_ERROR", "MCP server error") from exc
    finally:
        await http_client.aclose()
    tools = getattr(listed, "tools", listed) or []
    return [
        {
            "name": tool.name,
            "description": getattr(tool, "description", "") or "",
            "inputSchema": getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {},
        }
        for tool in tools
    ]
