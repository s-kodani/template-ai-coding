from __future__ import annotations

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
    )
    assert result == {"hits": []}
    assert seen == ["Bearer first", "Bearer second"]
