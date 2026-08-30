from __future__ import annotations

from typing import Self
from unittest.mock import AsyncMock

import httpx
import pytest

from chat_ui.gateway_client import MCPGatewayClient, call_default_tool


class _FakeManager:
    def __init__(self, tokens: list[str | None]) -> None:
        self._tokens = list(tokens)
        self.calls: list[bool] = []

    async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None:
        del session_id
        self.calls.append(force_refresh)
        return self._tokens.pop(0) if self._tokens else None


@pytest.mark.asyncio
async def test_call_tool_returns_token_expired_on_401(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MCPGatewayClient("http://gateway:8082")

    class FakeResponse:
        status_code = 401
        text = "expired"

        def json(self) -> dict:
            return {"code": "TOKEN_EXPIRED"}

    fake = AsyncMock()
    fake.__aenter__.return_value.post = AsyncMock(return_value=FakeResponse())
    fake.__aexit__.return_value = None
    monkeypatch.setattr("chat_ui.gateway_client.httpx.AsyncClient", lambda **_: fake)

    result = await client.call_tool("knowledge", "search_knowledge", {"query": "x"}, "tok")
    assert result["error"] == "TOKEN_EXPIRED"
    assert result["status_code"] == 401


@pytest.mark.asyncio
async def test_call_default_tool_retries_once_after_401(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload
            self.text = ""

        def json(self) -> dict:
            return self._payload

    async def fake_post(self: httpx.AsyncClient, url: str, headers: dict | None = None, json: dict | None = None):
        del self, url, json
        token = (headers or {}).get("Authorization", "")
        seen.append(token)
        if len(seen) == 1:
            return FakeResponse(401, {})
        return FakeResponse(200, {"hits": []})

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    result = await call_default_tool(
        MCPGatewayClient("http://gateway:8082"),
        _FakeManager(["first", "second"]),
        "sess",
        "search_knowledge",
        {"query": "docs"},
        server_id="knowledge",
    )
    assert result == {"hits": []}
    assert seen == ["Bearer first", "Bearer second"]


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
            {"id": "knowledge", "name": "knowledge-mcp", "tools": ["search_knowledge"]},
            {"id": "other", "name": "other", "tools": ["ping"]},
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
async def test_list_tools_returns_empty_on_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MCPGatewayClient("http://gateway:8082")

    class FakeResponse:
        status_code = 403
        text = "denied"

        def json(self) -> dict:
            return {"code": "ACCESS_DENIED"}

    fake = _GetClient([FakeResponse()])
    monkeypatch.setattr("chat_ui.gateway_client.httpx.AsyncClient", lambda **_: fake)
    assert await client.list_tools("knowledge", "tok") == []


@pytest.mark.asyncio
async def test_load_gateway_catalog_maps_tools_to_server_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from chat_ui.gateway_client import load_gateway_catalog

    client = MCPGatewayClient("http://gateway:8082")

    async def fake_list_servers(token: str) -> list[dict]:
        assert token == "tok"
        return [
            {"id": "knowledge", "name": "knowledge-mcp", "tools": ["search_knowledge"]},
            {"id": "other", "name": "other", "tools": ["ping"]},
        ]

    async def fake_list_tools(server_id: str, token: str) -> list[dict]:
        assert token == "tok"
        if server_id == "knowledge":
            return [
                {
                    "name": "search_knowledge",
                    "description": "Search",
                    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
                }
            ]
        return [{"name": "ping", "description": "Ping", "inputSchema": {"type": "object"}}]

    monkeypatch.setattr(client, "list_servers", fake_list_servers)
    monkeypatch.setattr(client, "list_tools", fake_list_tools)
    tools, targets = await load_gateway_catalog(client, "tok")
    assert [tool["function"]["name"] for tool in tools] == ["search_knowledge", "ping"]
    assert targets == {"search_knowledge": "knowledge", "ping": "other"}
