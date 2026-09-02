from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Self

import httpx
import pytest

from chat_ui.gateway_client import MCPGatewayClient, call_gateway_tool, load_gateway_catalog


class _FakeManager:
    def __init__(self, tokens: list[str | None]) -> None:
        self._tokens = list(tokens)
        self.calls: list[bool] = []

    async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None:
        del session_id
        self.calls.append(force_refresh)
        return self._tokens.pop(0) if self._tokens else None


class _FakeMcp:
    def __init__(
        self,
        *,
        tools: list[Any] | None = None,
        result: dict | None = None,
        error: BaseException | None = None,
    ) -> None:
        self.tools = tools or []
        self.result = result or {}
        self.error = error
        self.calls: list[tuple[str, dict, object]] = []
        self.url = ""
        self.token = ""

    async def __aenter__(self) -> Self:
        if self.error and not self.calls:
            raise self.error
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def list_tools(self) -> Any:
        if self.error:
            raise self.error
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict, meta: object = None) -> Any:
        self.calls.append((name, arguments, meta))
        if self.error:
            raise self.error
        return SimpleNamespace(
            is_error=False,
            content=[SimpleNamespace(text=json.dumps(self.result))],
        )


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://gateway:8082/mcp/knowledge")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("http error", request=request, response=response)


@pytest.mark.asyncio
async def test_call_tool_returns_token_expired_on_401() -> None:
    fake = _FakeMcp(error=_http_error(401))

    def factory(url: str, token: str) -> _FakeMcp:
        fake.url = url
        fake.token = token
        return fake

    client = MCPGatewayClient("http://gateway:8082", mcp_client_factory=factory)
    result = await client.call_tool("knowledge", "search_knowledge", {"query": "x"}, "tok")
    assert result["error"] == "TOKEN_EXPIRED"
    assert result["status_code"] == 401
    assert fake.url == "http://gateway:8082/mcp/knowledge"
    assert fake.token == "tok"


@pytest.mark.asyncio
async def test_call_tool_uses_catalog_url() -> None:
    fake = _FakeMcp(result={"ok": True})

    def factory(url: str, token: str) -> _FakeMcp:
        fake.url = url
        fake.token = token
        return fake

    client = MCPGatewayClient("http://gateway:8082", mcp_client_factory=factory)
    result = await client.call_tool(
        "knowledge",
        "search_knowledge",
        {"query": "x"},
        "tok",
        url="http://custom/mcp/knowledge",
    )
    assert result == {"ok": True}
    assert fake.url == "http://custom/mcp/knowledge"


@pytest.mark.asyncio
async def test_call_gateway_tool_requires_server_id() -> None:
    with pytest.raises(TypeError):
        await call_gateway_tool(  # type: ignore[misc]
            MCPGatewayClient("http://gateway:8082"),
            _FakeManager(["tok"]),
            "sess",
            "search_knowledge",
            {"query": "docs"},
        )


@pytest.mark.asyncio
async def test_call_gateway_tool_unauthenticated_is_generic() -> None:
    result = await call_gateway_tool(
        MCPGatewayClient("http://gateway:8082"),
        _FakeManager([None]),
        "sess",
        "search_knowledge",
        {"query": "docs"},
        server_id="other",
    )
    assert result == {"error": "Not authenticated for MCP tools"}


@pytest.mark.asyncio
async def test_call_gateway_tool_retries_once_after_401() -> None:
    calls: list[str] = []

    class _RetryMcp(_FakeMcp):
        async def __aenter__(self) -> Self:
            return self

        async def call_tool(self, name: str, arguments: dict, meta: object = None) -> Any:
            self.calls.append((name, arguments, meta))
            if len(calls) == 0:
                calls.append(self.token)
                raise _http_error(401)
            calls.append(self.token)
            return SimpleNamespace(
                is_error=False,
                content=[SimpleNamespace(text='{"hits": []}')],
            )

    current = _RetryMcp()

    def factory(url: str, token: str) -> _RetryMcp:
        current.url = url
        current.token = token
        return current

    result = await call_gateway_tool(
        MCPGatewayClient("http://gateway:8082", mcp_client_factory=factory),
        _FakeManager(["first", "second"]),
        "sess",
        "search_knowledge",
        {"query": "docs"},
        server_id="other",
    )
    assert result == {"hits": []}
    assert calls == ["first", "second"]
    assert current.url == "http://gateway:8082/mcp/other"


class _GetClient:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.urls: list[str] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get(self, url: str, headers: dict | None = None) -> object:
        del headers
        self.urls.append(url)
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_list_servers_returns_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MCPGatewayClient("http://gateway:8082")
    payload = {
        "servers": [
            {
                "id": "knowledge",
                "name": "knowledge-mcp",
                "tools": ["search_knowledge"],
                "url": "http://gateway:8082/mcp/knowledge",
            },
            {
                "id": "other",
                "name": "other",
                "tools": ["ping"],
                "url": "http://gateway:8082/mcp/other",
            },
        ]
    }

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return payload

    fake = _GetClient([FakeResponse()])
    monkeypatch.setattr("chat_ui.gateway_client.httpx.AsyncClient", lambda **_: fake)
    assert await client.list_servers("tok") == payload["servers"]
    assert fake.urls == ["http://gateway:8082/v1/mcp"]


@pytest.mark.asyncio
async def test_list_tools_returns_empty_on_forbidden() -> None:
    fake = _FakeMcp(error=_http_error(403))

    def factory(url: str, token: str) -> _FakeMcp:
        fake.url = url
        fake.token = token
        return fake

    client = MCPGatewayClient("http://gateway:8082", mcp_client_factory=factory)
    assert await client.list_tools("knowledge", "tok") == []
    assert fake.url == "http://gateway:8082/mcp/knowledge"


@pytest.mark.asyncio
async def test_load_gateway_catalog_uses_catalog_url() -> None:
    listed_urls: list[str] = []

    class CatalogClient(MCPGatewayClient):
        async def list_servers(self, token: str) -> list[dict]:
            assert token == "tok"
            return [
                {
                    "id": "knowledge",
                    "name": "knowledge-mcp",
                    "tools": ["search_knowledge"],
                    "url": "http://gateway:8082/mcp/knowledge",
                },
                {
                    "id": "other",
                    "name": "other",
                    "tools": ["ping"],
                    "url": "http://gateway:8082/mcp/other",
                },
            ]

        async def list_tools(
            self, server_id: str, token: str, url: str | None = None
        ) -> list[dict]:
            assert token == "tok"
            listed_urls.append(str(url))
            if server_id == "knowledge":
                return [
                    {
                        "name": "search_knowledge",
                        "description": "Search",
                        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    }
                ]
            return [{"name": "ping", "description": "Ping", "inputSchema": {"type": "object"}}]

    tools, targets = await load_gateway_catalog(CatalogClient("http://gateway:8082"), "tok")
    assert listed_urls == [
        "http://gateway:8082/mcp/knowledge",
        "http://gateway:8082/mcp/other",
    ]
    assert [tool["function"]["name"] for tool in tools] == [
        "knowledge__search_knowledge",
        "other__ping",
    ]
    assert targets == {
        "knowledge__search_knowledge": ("knowledge", "search_knowledge"),
        "other__ping": ("other", "ping"),
    }


@pytest.mark.asyncio
async def test_call_tool_injects_trace_meta(span_exporter) -> None:
    from opentelemetry import trace

    fake = _FakeMcp(result={"ok": True})

    def factory(url: str, token: str) -> _FakeMcp:
        fake.url = url
        fake.token = token
        return fake

    client = MCPGatewayClient("http://gateway:8082", mcp_client_factory=factory)
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("chat.turn"):
        result = await client.call_tool("knowledge", "search_knowledge", {"query": "x"}, "tok")
    assert result == {"ok": True}
    assert fake.calls[0][2] is not None
    assert "traceparent" in fake.calls[0][2]
