from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from chat_ui.gateway_client import MCPGatewayClient, resolve_gateway_url
from chat_ui.gateway_mcp_connect import (
    auto_connect_gateway_mcps,
    connect_gateway_mcp,
    disconnect_gateway_mcp,
    is_gateway_mcp_name,
    reconnect_gateway_mcp,
)


class _FakeManager:
    def __init__(self, tokens: list[str | None]) -> None:
        self._tokens = list(tokens)
        self.refresh_calls: list[bool] = []

    async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None:
        del session_id
        self.refresh_calls.append(force_refresh)
        return self._tokens.pop(0) if self._tokens else None


class _FakeSession:
    def __init__(self) -> None:
        self.id = "sess-1"
        self.mcp_sessions: dict[str, object] = {}
        self.user = SimpleNamespace(identifier="dev@localhost")

    def swap_mcp_session(self, name: str, obj: object) -> object | None:
        return self.mcp_sessions.pop(name, None)


def test_is_gateway_mcp_name() -> None:
    names = {"knowledge-mcp": "knowledge"}
    assert is_gateway_mcp_name("knowledge-mcp", names) is True
    assert is_gateway_mcp_name("other-mcp", names) is False


@pytest.mark.asyncio
async def test_resolve_gateway_url_returns_catalog_url() -> None:
    class CatalogClient(MCPGatewayClient):
        async def list_servers(self, token: str) -> list[dict]:
            assert token == "tok"
            return [
                {
                    "id": "knowledge",
                    "url": "http://gateway:8082/mcp/knowledge",
                }
            ]

    url = await resolve_gateway_url(CatalogClient("http://gateway:8082"), "knowledge", "tok")
    assert url == "http://gateway:8082/mcp/knowledge"


@pytest.mark.asyncio
async def test_resolve_gateway_url_missing_server() -> None:
    class EmptyClient(MCPGatewayClient):
        async def list_servers(self, token: str) -> list[dict]:
            del token
            return []

    url = await resolve_gateway_url(EmptyClient("http://gateway:8082"), "knowledge", "tok")
    assert url is None


@pytest.mark.asyncio
async def test_connect_gateway_mcp_not_authorized_by_catalog() -> None:
    session = _FakeSession()

    class EmptyClient(MCPGatewayClient):
        async def list_servers(self, token: str) -> list[dict]:
            del token
            return []

    with pytest.raises(HTTPException) as exc:
        await connect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=_FakeManager(["tok"]),
            gateway_client=EmptyClient("http://gateway:8082"),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_connect_gateway_mcp_unknown_name() -> None:
    session = _FakeSession()
    with pytest.raises(HTTPException) as exc:
        await connect_gateway_mcp(
            session,
            "missing",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=_FakeManager(["tok"]),
            gateway_client=MCPGatewayClient("http://gateway:8082"),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_connect_gateway_mcp_requires_auth() -> None:
    session = _FakeSession()
    with pytest.raises(HTTPException) as exc:
        await connect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=_FakeManager([None]),
            gateway_client=MCPGatewayClient("http://gateway:8082"),
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_disconnect_gateway_mcp_no_session() -> None:
    session = _FakeSession()
    result = await disconnect_gateway_mcp(session, "knowledge-mcp")
    assert result == {"success": True}


@pytest.mark.asyncio
async def test_reconnect_gateway_mcp_refreshes_token() -> None:
    session = _FakeSession()
    calls: list[bool] = []

    async def fake_connect(
        _session: object,
        ui_name: str,
        *,
        name_to_id: dict[str, str],
        token_manager: object,
        gateway_client: object,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        del ui_name, name_to_id, gateway_client
        calls.append(force_refresh)
        await token_manager.get_access_token("sess-1", force_refresh=force_refresh)  # type: ignore[union-attr]
        return {"success": True}

    with patch("chat_ui.gateway_mcp_connect.connect_gateway_mcp", fake_connect):
        await reconnect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=_FakeManager(["new-token"]),
            gateway_client=MCPGatewayClient("http://gateway:8082"),
        )
    assert calls == [True]


@pytest.mark.asyncio
async def test_auto_connect_gateway_mcps_connects_allowed_servers() -> None:
    session = _FakeSession()
    connected: list[str] = []

    async def fake_connect(
        _session: object,
        ui_name: str,
        **kwargs: object,
    ) -> dict[str, object]:
        del kwargs
        connected.append(ui_name)
        return {"success": True}

    class CatalogClient(MCPGatewayClient):
        async def list_servers(self, token: str) -> list[dict]:
            assert token == "tok"
            return [{"id": "knowledge"}, {"id": "other"}]

    with patch("chat_ui.gateway_mcp_connect.connect_gateway_mcp", fake_connect):
        names = await auto_connect_gateway_mcps(
            session,
            name_to_id={"knowledge-mcp": "knowledge", "other-mcp": "other"},
            id_to_name={"knowledge": "knowledge-mcp", "other": "other-mcp"},
            token_manager=_FakeManager(["tok"]),
            gateway_client=CatalogClient("http://gateway:8082"),
        )
    assert names == ["knowledge-mcp", "other-mcp"]
    assert connected == ["knowledge-mcp", "other-mcp"]
