"""Tracing hooks for the pinned Open WebUI version; no Host/UI implementation."""

from __future__ import annotations

import codecs
import contextvars
import functools
import inspect
import json
import os
from dataclasses import dataclass
from typing import Any

from langfuse import Langfuse, get_client, observe, propagate_attributes
from langfuse.span_filter import is_default_export_span
from opentelemetry import context as otel_context
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.responses import StreamingResponse

_client: Langfuse | None = None


@dataclass
class Turn:
    output: str = ""
    closed: bool = False


_turn: contextvars.ContextVar[Turn | None] = contextvars.ContextVar("openwebui_turn", default=None)


def enabled() -> bool:
    return (
        os.getenv("LANGFUSE_TRACING_ENABLED", "true").lower() == "true"
        and bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
        and bool(os.getenv("LANGFUSE_SECRET_KEY"))
    )


def client() -> Langfuse:
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
            environment=os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or None,
            release=os.getenv("LANGFUSE_RELEASE") or None,
            should_export_span=should_export_span,
        )
    return _client


def should_export_span(span) -> bool:
    # MCP SDK 2 injects its CLIENT span ID into _meta. Export that parent too,
    # or downstream server observations would point to a missing observation.
    return is_default_export_span(span) or bool(
        span.parent is not None
        and span.instrumentation_scope is not None
        and span.instrumentation_scope.name == "mcp-python-sdk"
    )


def inject_trace() -> dict[str, str] | None:
    carrier: dict[str, str] = {}
    TraceContextTextMapPropagator().inject(carrier)
    W3CBaggagePropagator().inject(carrier)
    return carrier or None


def user_id(user: Any) -> str | None:
    value = user if isinstance(user, dict) else vars(user) if user is not None else {}
    oauth = value.get("oauth") or {}
    providers = [oauth.get("oidc"), *[item for key, item in oauth.items() if key != "oidc"]]
    for provider in providers:
        if isinstance(provider, dict) and provider.get("sub"):
            return str(provider["sub"])
    return str(value["id"]) if value.get("id") else None


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if any(
                part in key.lower() for part in ("token", "authorization", "api_key", "embedding")
            )
            else sanitize(item)
            for key, item in value.items()
            if key != "_meta"
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return value if len(value) <= 500 else value[:500].rstrip() + "…"
        if isinstance(parsed, (dict, list)):
            return json.dumps(sanitize(parsed), ensure_ascii=False)
        return value if len(value) <= 500 else value[:500].rstrip() + "…"
    return value


def _arguments(function, args, kwargs) -> dict:
    return inspect.signature(function).bind_partial(*args, **kwargs).arguments


def _preserve_signature(wrapper, function):
    # FastAPI resolves forward annotations using the endpoint signature.
    wrapper.__signature__ = inspect.signature(function, eval_str=True)
    return wrapper


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def trace_chat_turn(function):
    @observe(name="chat.turn", capture_input=False, capture_output=False)
    async def observed(*args, **kwargs):
        values = _arguments(function, args, kwargs)
        messages = values.get("form_data", {}).get("messages", [])
        last_user = next(
            (message for message in reversed(messages) if message.get("role") == "user"), {}
        )
        client().update_current_span(input={"content": sanitize(_text(last_user.get("content")))})
        state = _turn.get()
        try:
            return await function(*args, **kwargs)
        finally:
            if state is not None:
                client().update_current_span(output={"content": state.output})

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        if not enabled():
            return await function(*args, **kwargs)
        client()
        values = _arguments(function, args, kwargs)
        form_data = values.get("form_data", {})
        metadata = values.get("metadata") or form_data.get("metadata") or {}
        state = Turn()
        turn_token = _turn.set(state)
        context_token = otel_context.attach(otel_context.Context())
        try:
            with propagate_attributes(
                user_id=user_id(values.get("user")),
                session_id=metadata.get("chat_id"),
                tags=["open-webui"],
                metadata={"component": "open-webui", "chat_model": form_data.get("model", "")},
                as_baggage=True,
            ):
                return await observed(
                    *args, **kwargs, langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"]
                )
        finally:
            state.closed = True
            otel_context.detach(context_token)
            _turn.reset(turn_token)

    return _preserve_signature(wrapper, function)


def _usage(payload: dict, model: str) -> None:
    usage = payload.get("usage") or {}
    names = {
        "prompt_tokens": "input",
        "completion_tokens": "output",
        "total_tokens": "total",
        "input_tokens": "input",
        "output_tokens": "output",
    }
    details = {
        target: int(usage[key]) for key, target in names.items() if usage.get(key) is not None
    }
    get_client().update_current_generation(
        model=payload.get("model") or model, usage_details=details or None
    )
    state = _turn.get()
    if state is not None:
        for choice in payload.get("choices", []):
            message = choice.get("delta") or choice.get("message") or {}
            content = _text(message.get("content"))
            if content and len(state.output) <= 500:
                state.output = (state.output + content)[:501]
                if len(state.output) > 500:
                    state.output = state.output[:500] + "…"


async def _observe_sse(iterator, model):
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    pending = ""
    try:
        async for chunk in iterator:
            pending += decoder.decode(chunk) if isinstance(chunk, bytes) else str(chunk)
            pending = pending.replace("\r\n", "\n")
            while "\n\n" in pending:
                event, pending = pending.split("\n\n", 1)
                data = "\n".join(
                    line[5:].lstrip() for line in event.splitlines() if line.startswith("data:")
                )
                try:
                    payload = json.loads(data)
                except ValueError:
                    continue
                if isinstance(payload, dict):
                    _usage(payload, model)
            # Bound incomplete/malformed events; tool argument bodies are never captured.
            if len(pending) > 65536:
                pending = ""
            yield chunk
    finally:
        close = getattr(iterator, "aclose", None)
        if close is not None:
            await close()


def trace_generation(function):
    @observe(name="llm.generate", as_type="generation", capture_input=False, capture_output=False)
    async def observed(*args, **kwargs):
        values = _arguments(function, args, kwargs)
        model = values.get("form_data", {}).get("model", "")
        state = _turn.get()
        if state is not None:
            state.output = ""
        get_client().update_current_generation(model=model)
        result = await function(*args, **kwargs)
        if isinstance(result, StreamingResponse):
            result.body_iterator = _observe_sse(result.body_iterator, model)
        elif isinstance(result, dict):
            _usage(result, model)
        return result

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        state = _turn.get()
        if not enabled() or state is None or state.closed:
            return await function(*args, **kwargs)
        return await observed(
            *args, **kwargs, langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"]
        )

    return _preserve_signature(wrapper, function)


def trace_mcp_tool(function):
    @observe(name="mcp.tool", as_type="tool", capture_input=False, capture_output=False)
    async def observed(*args, **kwargs):
        values = _arguments(function, args, kwargs)
        name = values.get("function_name", "mcp.tool")
        owner = values.get("self")
        get_client().update_current_span(
            name=name,
            input=sanitize(values.get("function_args", {})),
            metadata={
                "tool.route": "gateway",
                "tool.server_id": getattr(owner, "server_name", ""),
                "tool.mcp_name": name,
            },
        )
        result = await function(*args, **kwargs)
        get_client().update_current_span(output=sanitize(result))
        return result

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        if not enabled():
            return await function(*args, **kwargs)
        client()
        return await observed(
            *args, **kwargs, langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"]
        )

    return _preserve_signature(wrapper, function)


def trace_app_rpc(function):
    @observe(name="mcp.app", capture_input=False, capture_output=False)
    async def observed(*args, **kwargs):
        values = _arguments(function, args, kwargs)
        form = values.get("form_data")
        get_client().update_current_span(
            metadata={"method": getattr(form, "method", ""), "server": values.get("id", "")}
        )
        return await function(*args, **kwargs)

    @functools.wraps(function)
    async def wrapper(*args, **kwargs):
        if not enabled():
            return await function(*args, **kwargs)
        client()
        values = _arguments(function, args, kwargs)
        context_token = otel_context.attach(otel_context.Context())
        try:
            with propagate_attributes(
                user_id=user_id(values.get("user")),
                tags=["open-webui", "mcp-app"],
                metadata={"component": "open-webui"},
                as_baggage=True,
            ):
                return await observed(
                    *args, **kwargs, langfuse_public_key=os.environ["LANGFUSE_PUBLIC_KEY"]
                )
        finally:
            otel_context.detach(context_token)

    return _preserve_signature(wrapper, function)
