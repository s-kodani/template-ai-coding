from __future__ import annotations

import os
from typing import Any

from langfuse import Langfuse, get_client

_langfuse_client: Langfuse | None = None
_langfuse_enabled = False
_TRACE_OUTPUT_MAX_CONTENT_LENGTH = 500


def configure_langfuse_tracing() -> Langfuse | None:
    global _langfuse_client, _langfuse_enabled
    if _langfuse_client is not None:
        return _langfuse_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3000").strip()
    enabled = os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() not in {"0", "false", "no"}
    if not enabled or not public_key or not secret_key:
        _langfuse_enabled = False
        return None

    _langfuse_client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
        environment=os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or None,
        release=os.getenv("LANGFUSE_RELEASE") or None,
    )
    _langfuse_enabled = True
    return _langfuse_client


def record_tool_input(payload: dict[str, Any]) -> None:
    if not _langfuse_enabled:
        return
    client = get_client()
    if client is None:
        return
    client.update_current_span(input=payload)


def record_tool_output(payload: dict[str, Any]) -> None:
    if not _langfuse_enabled:
        return
    client = get_client()
    if client is None:
        return
    output = _truncate_output(payload)
    client.update_current_span(output=output)


def _truncate_output(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results")
    if not isinstance(results, list):
        return payload
    trimmed: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        snippet = str(item.get("snippet") or "")
        if len(snippet) > _TRACE_OUTPUT_MAX_CONTENT_LENGTH:
            item = {**item, "snippet": snippet[:_TRACE_OUTPUT_MAX_CONTENT_LENGTH]}
        trimmed.append(item)
    return {**payload, "results": trimmed}
