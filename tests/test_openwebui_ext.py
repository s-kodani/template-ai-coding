from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from starlette.responses import StreamingResponse


def test_bootstrap_builds_role_scoped_connections_and_native_model():
    from open_webui_ext.startup import configured_environment

    registry = {
        "gateways": [
            {
                "url": "http://gateway:8082",
                "servers": {
                    "knowledge": {
                        "enabled": True,
                        "ui": {"name": "knowledge-mcp"},
                        "authorization": {"required_roles": ["knowledge-mcp-reader"]},
                    },
                    "web-search": {
                        "enabled": True,
                        "ui": {"name": "web-search-mcp"},
                        "authorization": {"required_roles": ["web-search-reader"]},
                    },
                    "disabled": {"enabled": False},
                },
            }
        ]
    }
    env = configured_environment(
        {"CHAT_MODEL": "test-model", "OPENAI_BASE_URL": "http://llm/v1"}, registry
    )
    connections = json.loads(env["TOOL_SERVER_CONNECTIONS"])
    assert [item["url"] for item in connections] == [
        "http://gateway:8082/mcp/knowledge",
        "http://gateway:8082/mcp/web-search",
    ]
    assert connections[0]["auth_type"] == "system_oauth"
    assert connections[0]["config"]["access_grants"] == [
        {"principal_type": "group", "principal_id": "knowledge-mcp-reader", "permission": "read"}
    ]
    assert json.loads(env["DEFAULT_MODEL_METADATA"])["toolIds"] == [
        "server:mcp:knowledge",
        "server:mcp:web-search",
    ]
    assert json.loads(env["DEFAULT_MODEL_PARAMS"])["function_calling"] == "native"
    assert json.loads(env["OPENAI_API_CONFIGS"])["0"]["model_ids"] == ["test-model"]
    assert env["ENABLE_OTEL"] == "false"


@pytest.mark.asyncio
async def test_seed_groups_is_idempotent_and_preserves_unrelated_groups():
    from open_webui_ext.startup import ensure_groups

    rows = {"other": {"id": "other", "name": "existing"}}

    async def find(group_id):
        return rows.get(group_id)

    async def insert(group_id, name):
        rows[group_id] = {"id": group_id, "name": name}

    await ensure_groups(find, insert)
    await ensure_groups(find, insert)
    assert rows == {
        "other": {"id": "other", "name": "existing"},
        "knowledge-mcp-reader": {"id": "knowledge-mcp-reader", "name": "knowledge-mcp-reader"},
        "web-search-reader": {"id": "web-search-reader", "name": "web-search-reader"},
    }


@pytest.fixture
def trace_runtime(monkeypatch):
    from langfuse import Langfuse

    from open_webui_ext import tracing

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    public_key = "pk-openwebui-tests-" + str(uuid4())
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", public_key)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-openwebui-tests")
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    client = Langfuse(
        public_key=public_key,
        secret_key="sk-openwebui-tests",
        tracer_provider=provider,
        should_export_span=lambda _: False,
    )
    monkeypatch.setattr(tracing, "_client", client)
    yield tracing, exporter
    client.flush()
    exporter.clear()


def test_native_mcp_wire_parent_is_exported_without_unrelated_spans(monkeypatch):
    from langfuse import Langfuse
    from opentelemetry import trace
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    from open_webui_ext import tracing

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    public_key = "pk-mcp-export-test-" + str(uuid4())
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", public_key)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_TRACING_ENABLED", "true")
    monkeypatch.setattr(tracing, "_client", None)
    monkeypatch.setattr(
        tracing,
        "Langfuse",
        lambda **kwargs: Langfuse(
            **kwargs, tracer_provider=provider, span_exporter=exporter
        ),
    )
    client = tracing.client()
    mcp_tracer = provider.get_tracer("mcp-python-sdk")
    with client.start_as_current_observation(name="chat.turn"):
        with mcp_tracer.start_as_current_span("MCP send tools/call search_knowledge"):
            carrier = {}
            TraceContextTextMapPropagator().inject(carrier)
            wire_parent = trace.get_current_span().get_span_context().span_id
        with provider.get_tracer("unrelated.http").start_as_current_span("unrelated"):
            pass
    with mcp_tracer.start_as_current_span("MCP send initialize"):
        pass
    client.flush()
    spans = exporter.get_finished_spans()
    by_id = {span.context.span_id: span for span in spans}
    assert wire_parent in by_id, "The SDK injects this parent ID into outgoing MCP _meta"
    native = by_id[wire_parent]
    assert by_id[native.parent.span_id].name == "chat.turn"
    assert {span.name for span in spans} == {
        "chat.turn", "MCP send tools/call search_knowledge"
    }
    assert carrier["traceparent"].split("-")[2] == f"{wire_parent:016x}"


def test_mcp_meta_rejects_oversized_traceparent_and_keeps_valid_parent():
    from opentelemetry import trace
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    propagator = TraceContextTextMapPropagator()
    parent = "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"
    valid = trace.get_current_span(propagator.extract({"traceparent": parent}))
    assert valid.get_span_context().is_valid
    oversized = trace.get_current_span(
        propagator.extract({"traceparent": parent + " " * 512})
    )
    assert not oversized.get_span_context().is_valid


@pytest.mark.asyncio
async def test_parallel_turns_keep_user_session_and_mcp_parent_separate(trace_runtime):
    tracing, exporter = trace_runtime

    class Client:
        server_name = "knowledge"

        @tracing.trace_mcp_tool
        async def call_tool_raw(self, function_name, function_args):
            await asyncio.sleep(0)
            return {"structuredContent": {"content": "x" * 1000}, "_meta": {"token": "secret"}}

    observed = []

    @tracing.trace_chat_turn
    async def process_chat(request, form_data, user, metadata, model, tasks=None):
        @tracing.trace_generation
        async def generate(request, form_data, user):
            await asyncio.sleep(0)
            return {
                "model": "test-model",
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            }

        await generate(request, form_data, user)
        await Client().call_tool_raw("get_document", {"document_id": "doc"})
        observed.append((user.oauth["oidc"]["sub"], tracing.inject_trace()))

    async def turn(name):
        await process_chat(
            SimpleNamespace(),
            {"model": "test-model", "messages": [{"role": "user", "content": "question"}]},
            SimpleNamespace(id="local-" + name, oauth={"oidc": {"sub": name}}),
            {"chat_id": "chat-" + name},
            {},
        )

    await asyncio.gather(turn("alice"), turn("bob"))
    spans = exporter.get_finished_spans()
    roots = [span for span in spans if span.name == "chat.turn"]
    assert len(roots) == 2
    assert len({span.context.trace_id for span in roots}) == 2
    for root in roots:
        user = root.attributes["user.id"]
        assert user in {"alice", "bob"}
        assert root.attributes["session.id"] == "chat-" + user
        children = [
            span
            for span in spans
            if span.context.trace_id == root.context.trace_id and span is not root
        ]
        assert {span.name for span in children} == {"llm.generate", "get_document"}
        assert all(span.parent.span_id == root.context.span_id for span in children)
    assert all("traceparent" in meta and "baggage" in meta for _, meta in observed)
    assert "secret" not in str([dict(span.attributes) for span in spans])
    assert "x" * 501 not in str([dict(span.attributes) for span in spans])
    generations = [span for span in spans if span.name == "llm.generate"]
    assert all(
        json.loads(span.attributes["langfuse.observation.usage_details"])["total"] == 10
        for span in generations
    )


@pytest.mark.asyncio
async def test_generation_span_stays_open_until_stream_consumed(trace_runtime):
    tracing, exporter = trace_runtime

    @tracing.trace_generation
    async def generate(request, form_data, user):
        async def chunks():
            yield b'data: {"choices":[{"delta":{"content":"answer"}}]}\n\n'
            yield b'data: {"usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3}}\n\n'

        return StreamingResponse(chunks())

    @tracing.trace_chat_turn
    async def turn(request, form_data, user, metadata, model):
        response = await generate(request, form_data, user)
        assert not [span for span in exporter.get_finished_spans() if span.name == "llm.generate"]
        chunks = [chunk async for chunk in response.body_iterator]
        assert len(chunks) == 2

    await turn(
        SimpleNamespace(),
        {"model": "model", "messages": []},
        SimpleNamespace(id="u", oauth={}),
        {"chat_id": "chat"},
        {},
    )
    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["llm.generate", "chat.turn"]
    generation = spans[0]
    assert json.loads(generation.attributes["langfuse.observation.usage_details"]) == {
        "input": 2,
        "output": 1,
        "total": 3,
    }


@pytest.mark.asyncio
async def test_cancelled_turn_ends_root_span(trace_runtime):
    tracing, exporter = trace_runtime
    started = asyncio.Event()

    @tracing.trace_chat_turn
    async def turn(request, form_data, user, metadata, model):
        started.set()
        await asyncio.Future()

    task = asyncio.create_task(
        turn(
            SimpleNamespace(),
            {"model": "m", "messages": []},
            SimpleNamespace(id="u", oauth={}),
            {"chat_id": "c"},
            {},
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len([span for span in exporter.get_finished_spans() if span.name == "chat.turn"]) == 1


@pytest.mark.asyncio
async def test_stream_close_ends_generation_and_closes_upstream(trace_runtime):
    tracing, exporter = trace_runtime
    closed = asyncio.Event()

    @tracing.trace_generation
    async def generate(request, form_data, user):
        async def chunks():
            try:
                yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
                await asyncio.Future()
            finally:
                closed.set()

        return StreamingResponse(chunks())

    @tracing.trace_chat_turn
    async def turn(request, form_data, user, metadata, model):
        response = await generate(request, form_data, user)
        await anext(response.body_iterator)
        await response.body_iterator.aclose()

    await turn(
        SimpleNamespace(),
        {"model": "model", "messages": []},
        SimpleNamespace(id="u", oauth={}),
        {"chat_id": "chat"},
        {},
    )
    assert closed.is_set()
    assert [span.name for span in exporter.get_finished_spans()] == ["llm.generate", "chat.turn"]


@pytest.mark.asyncio
async def test_app_callback_has_own_root_and_preserves_viewer_identity(trace_runtime):
    tracing, exporter = trace_runtime

    @tracing.trace_app_rpc
    async def app_rpc(request, id, form_data, user):
        return {"html": "<p>private resource</p>"}

    result = await app_rpc(
        SimpleNamespace(),
        "server:mcp:knowledge",
        SimpleNamespace(method="ui/resource"),
        SimpleNamespace(id="local", oauth={"oidc": {"sub": "viewer"}}),
    )
    assert "html" in result
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "mcp.app"
    assert spans[0].parent is None
    assert spans[0].attributes["user.id"] == "viewer"
    assert "private resource" not in str(dict(spans[0].attributes))


@pytest.mark.asyncio
async def test_default_model_is_provisioned_with_authenticated_read_access_only_once():
    from open_webui_ext.startup import ensure_default_model

    entries = {}
    grants = set()

    async def find(model_id):
        return entries.get(model_id)

    async def insert(payload):
        entries[payload["id"]] = {**payload, "user_id": "system"}
        for grant in payload["access_grants"]:
            grants.add((grant["principal_type"], grant["principal_id"], grant["permission"]))

    async def grant(model_id):
        assert model_id == "test-model"
        grants.add(("user", "*", "read"))

    await ensure_default_model(
        "test-model",
        {"toolIds": ["server:mcp:knowledge"]},
        {"function_calling": "native"},
        find,
        insert,
        grant,
    )
    entries["test-model"]["name"] = "Administrator's display name"
    await ensure_default_model("test-model", {}, {}, find, insert, grant)
    assert len(entries) == 1
    assert entries["test-model"]["name"] == "Administrator's display name"
    assert entries["test-model"]["base_model_id"] is None
    assert entries["test-model"]["meta"]["toolIds"] == ["server:mcp:knowledge"]
    assert entries["test-model"]["params"]["function_calling"] == "native"
    assert grants == {("user", "*", "read")}


@pytest.mark.asyncio
async def test_existing_admin_model_is_not_reconfigured_or_made_public():
    from open_webui_ext.startup import ensure_default_model

    async def find(model_id):
        return {"id": model_id, "user_id": "administrator"}

    async def forbidden(*_):
        raise AssertionError("Administrator model must remain unchanged")

    await ensure_default_model("test-model", {}, {}, find, forbidden, forbidden)
