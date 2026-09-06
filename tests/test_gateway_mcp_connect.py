from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from chat_ui.gateway_client import MCPGatewayClient, resolve_gateway_url
from chat_ui.gateway_mcp_connect import (
    access_token_for_gateway_session,
    auto_connect_gateway_mcps,
    bind_gateway_request_user,
    connect_gateway_mcp,
    disconnect_gateway_mcp,
    existing_gateway_mcp_result,
    gateway_cookie_token,
    gateway_mcp_auth_response,
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


def test_gateway_cookie_token_reads_request_cookies_not_scope() -> None:
    def scope_get(_key: str, default: object = None) -> object:
        return default

    request = SimpleNamespace(cookies={"access_token": "jwt-here"}, get=scope_get)
    assert request.get("access_token") is None
    assert gateway_cookie_token(request) == "jwt-here"


def test_gateway_mcp_auth_response_is_not_401() -> None:
    response = gateway_mcp_auth_response()
    assert response.status_code == 403


def test_bind_gateway_request_user_attaches_when_session_user_missing() -> None:
    session = _FakeSession()
    session.user = None
    user = SimpleNamespace(identifier="dev@localhost")
    assert bind_gateway_request_user(session, user) is True
    assert session.user is user


def test_bind_gateway_request_user_copies_keycloak_sub() -> None:
    session = _FakeSession()
    session.user = SimpleNamespace(identifier="dev@localhost", metadata={})
    current = SimpleNamespace(identifier="dev@localhost", metadata={"keycloak_sub": "sub-1"})
    assert bind_gateway_request_user(session, current) is True
    assert session.user.metadata["keycloak_sub"] == "sub-1"


def test_bind_gateway_request_user_rejects_identifier_mismatch() -> None:
    session = _FakeSession()
    other = SimpleNamespace(identifier="other@localhost")
    assert bind_gateway_request_user(session, other) is False


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
async def test_existing_gateway_mcp_result_reuses_tuple_session() -> None:
    async def list_tools() -> SimpleNamespace:
        return SimpleNamespace(tools=[SimpleNamespace(name="search_knowledge")])

    session = _FakeSession()
    session.mcp_sessions["knowledge-mcp"] = (SimpleNamespace(list_tools=list_tools), object())
    result = await existing_gateway_mcp_result(session, "knowledge-mcp")
    assert result is not None
    assert result["success"] is True
    assert result["mcp"]["name"] == "knowledge-mcp"
    assert result["mcp"]["tools"] == [{"name": "search_knowledge"}]


@pytest.mark.asyncio
async def test_existing_gateway_mcp_result_reuses_client_attribute() -> None:
    async def list_tools() -> SimpleNamespace:
        return SimpleNamespace(tools=[SimpleNamespace(name="search_knowledge")])

    session = _FakeSession()
    session.mcp_sessions["knowledge-mcp"] = SimpleNamespace(
        client=SimpleNamespace(list_tools=list_tools)
    )
    result = await existing_gateway_mcp_result(session, "knowledge-mcp")
    assert result is not None
    assert result["mcp"]["tools"] == [{"name": "search_knowledge"}]


@pytest.mark.asyncio
async def test_access_token_for_gateway_session_binds_keycloak_sub() -> None:
    class BindAfterMiss:
        def __init__(self) -> None:
            self.bound: list[tuple[str, str]] = []
            self.by_session: dict[str, str] = {}

        async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None:
            del force_refresh
            return self.by_session.get(session_id)

        async def bind_session(self, subject: str, session_id: str) -> None:
            self.bound.append((subject, session_id))
            self.by_session[session_id] = "tok"

    session = _FakeSession()
    session.user = SimpleNamespace(identifier="dev@localhost", metadata={"keycloak_sub": "sub-1"})
    manager = BindAfterMiss()
    token = await access_token_for_gateway_session(session, manager)
    assert token == "tok"
    assert manager.bound == [("sub-1", "sess-1")]


@pytest.mark.asyncio
async def test_connect_reuses_existing_session_when_token_missing() -> None:
    async def list_tools() -> SimpleNamespace:
        return SimpleNamespace(tools=[SimpleNamespace(name="search_knowledge")])

    session = _FakeSession()
    session.mcp_sessions["knowledge-mcp"] = (SimpleNamespace(list_tools=list_tools), object())
    result = await connect_gateway_mcp(
        session,
        "knowledge-mcp",
        name_to_id={"knowledge-mcp": "knowledge"},
        token_manager=_FakeManager([None]),
        gateway_client=MCPGatewayClient("http://gateway:8082"),
    )
    assert result["success"] is True
    assert result["mcp"]["name"] == "knowledge-mcp"


@pytest.mark.asyncio
async def test_connect_binds_session_then_uses_catalog() -> None:
    class BindAfterMiss:
        def __init__(self) -> None:
            self.by_session: dict[str, str] = {}

        async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None:
            del force_refresh
            return self.by_session.get(session_id)

        async def bind_session(self, subject: str, session_id: str) -> None:
            assert subject == "sub-1"
            self.by_session[session_id] = "tok"

    class EmptyClient(MCPGatewayClient):
        async def list_servers(self, token: str) -> list[dict]:
            assert token == "tok"
            return []

    session = _FakeSession()
    session.user = SimpleNamespace(identifier="dev@localhost", metadata={"keycloak_sub": "sub-1"})
    with pytest.raises(HTTPException) as exc:
        await connect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=BindAfterMiss(),
            gateway_client=EmptyClient("http://gateway:8082"),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "Gateway MCP not authorized"


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
    assert exc.value.status_code == 403


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
