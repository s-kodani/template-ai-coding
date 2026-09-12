from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from chat_ui.gateway_client import MCPGatewayClient, resolve_gateway_url
from chat_ui.gateway_mcp_connect import (
    access_token_for_gateway_session,
    bind_gateway_request_user,
    connect_gateway_mcp,
    disconnect_gateway_mcp,
    existing_gateway_mcp_result,
    gateway_cookie_token,
    gateway_mcp_auth_response,
    is_gateway_mcp_name,
    reconnect_gateway_mcp,
)
from chat_ui.token_manager import REAUTH_REQUIRED_DETAIL, ReauthRequired


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
    assert result["mcp"]["url"] == "via MCP Gateway"
    assert result["mcp"]["status"] == "connected"

    labeled = await existing_gateway_mcp_result(
        session, "knowledge-mcp", gateway_url="http://mcp-gateway:8082/mcp/knowledge"
    )
    assert labeled is not None
    assert labeled["mcp"]["url"] == "via mcp-gateway:8082"


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
        name_to_gateway_url={"knowledge-mcp": "http://mcp-gateway:8082"},
    )
    assert result["success"] is True
    assert result["mcp"]["name"] == "knowledge-mcp"
    assert result["mcp"]["url"] == "via mcp-gateway:8082"
    assert result["mcp"]["status"] == "connected"


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
    # A second attempt after the dead tokens were dropped must stay actionable
    # instead of falling back to the old generic wording.
    assert exc.value.detail == REAUTH_REQUIRED_DETAIL


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
        name_to_gateway_url: dict[str, str] | None = None,
    ) -> dict[str, object]:
        del ui_name, name_to_id, gateway_client, name_to_gateway_url
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
async def test_connect_reuse_invokes_on_mcp_connect() -> None:
    called: list[str] = []

    async def hook(connection: SimpleNamespace, client: object) -> None:
        called.append(connection.name)
        await client.list_tools()  # type: ignore[union-attr]

    async def list_tools() -> SimpleNamespace:
        return SimpleNamespace(tools=[SimpleNamespace(name="search_knowledge")])

    session = _FakeSession()
    session.mcp_sessions["knowledge-mcp"] = (SimpleNamespace(list_tools=list_tools), object())
    with patch("chainlit.config.config") as config:
        config.code.on_mcp_connect = hook
        result = await connect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=_FakeManager([None]),
            gateway_client=MCPGatewayClient("http://gateway:8082"),
            name_to_gateway_url={"knowledge-mcp": "http://mcp-gateway:8082"},
        )
    assert called == ["knowledge-mcp"]
    assert result["mcp"]["status"] == "connected"


@pytest.mark.asyncio
async def test_existing_gateway_mcp_result_returns_none_on_list_tools_timeout() -> None:
    async def list_tools() -> SimpleNamespace:
        await asyncio.sleep(1)
        return SimpleNamespace(tools=[SimpleNamespace(name="search_knowledge")])

    session = _FakeSession()
    session.mcp_sessions["knowledge-mcp"] = (SimpleNamespace(list_tools=list_tools), object())
    with patch("chat_ui.gateway_mcp_connect.LIST_TOOLS_TIMEOUT", 0.01):
        result = await existing_gateway_mcp_result(session, "knowledge-mcp")
    assert result is None


@pytest.mark.asyncio
async def test_connect_gateway_mcp_serializes_concurrent_reuse() -> None:
    in_flight = 0
    max_in_flight = 0

    async def list_tools() -> SimpleNamespace:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return SimpleNamespace(tools=[SimpleNamespace(name="search_knowledge")])

    session = _FakeSession()
    session.mcp_sessions["knowledge-mcp"] = (SimpleNamespace(list_tools=list_tools), object())

    async def once() -> dict[str, object]:
        return await connect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=_FakeManager([None]),
            gateway_client=MCPGatewayClient("http://gateway:8082"),
        )

    await asyncio.gather(once(), once())
    assert max_in_flight == 1


def test_on_chat_start_does_not_clear_mcp_tools() -> None:
    source = Path("src/chat_ui/app.py").read_text()
    tree = ast.parse(source)
    func = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "on_chat_start"
    )
    body = ast.get_source_segment(source, func) or ""
    assert 'set("mcp_tools", {})' not in body
    assert 'set("gateway_server_by_connection", {})' not in body
    assert "auto_connect_gateway_mcps" not in body


@pytest.mark.asyncio
async def test_connect_asks_for_relogin_when_keycloak_session_expired() -> None:
    class ExpiredManager:
        async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str:
            del session_id, force_refresh
            raise ReauthRequired("Keycloak session expired")

    session = _FakeSession()
    with pytest.raises(HTTPException) as exc:
        await connect_gateway_mcp(
            session,
            "knowledge-mcp",
            name_to_id={"knowledge-mcp": "knowledge"},
            token_manager=ExpiredManager(),
            gateway_client=MCPGatewayClient("http://gateway:8082"),
        )
    # 401 would make Chainlit redirect to /login and reload-loop.
    assert exc.value.status_code == 403
    assert exc.value.detail == REAUTH_REQUIRED_DETAIL


def test_dispatch_tool_reports_reconnect_failure_instead_of_raising() -> None:
    source = Path("src/chat_ui/app.py").read_text()
    tree = ast.parse(source)
    func = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_dispatch_tool"
    )
    handlers = [
        handler
        for node in ast.walk(func)
        if isinstance(node, ast.Try)
        for handler in node.handlers
        if isinstance(handler.type, ast.Name) and handler.type.id == "HTTPException"
    ]
    assert handlers, "_dispatch_tool must turn connect/reconnect 4xx into a tool result"
    assert all(
        any(isinstance(stmt, ast.Return) for stmt in ast.walk(handler))
        for handler in handlers
    ), "the handler must return the failure to the caller, not swallow it"
