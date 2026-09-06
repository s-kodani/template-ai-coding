from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from contextlib import AsyncExitStack
from types import SimpleNamespace
from typing import Any, Protocol, cast

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Message

from chat_ui.gateway_client import MCPGatewayClient, resolve_gateway_url
from chat_ui.mcp_ui import GATEWAY_MCP_TYPE, gateway_display_url

LIST_TOOLS_TIMEOUT = 5.0
GATEWAY_MCP_STATUS_CONNECTED = "connected"
_connect_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _connect_lock(session_id: str, ui_name: str) -> asyncio.Lock:
    key = (session_id, ui_name)
    lock = _connect_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _connect_locks[key] = lock
    return lock


class _CachedToolClient:
    def __init__(self, tool_list: Any) -> None:
        self._tool_list = tool_list

    async def list_tools(self) -> Any:
        return self._tool_list


class AccessTokenSource(Protocol):
    async def get_access_token(
        self, session_id: str, *, force_refresh: bool = False
    ) -> str | None: ...


def is_gateway_mcp_name(name: str, name_to_id: dict[str, str]) -> bool:
    return name in name_to_id


def _mcp_client_from_entry(entry: Any) -> Any:
    if isinstance(entry, (tuple, list)) and entry:
        return entry[0]
    client = getattr(entry, "client", None)
    if client is not None:
        return client
    if hasattr(entry, "list_tools"):
        return entry
    return None


async def existing_gateway_mcp_result(
    session: Any, ui_name: str, *, gateway_url: str | None = None
) -> dict[str, Any] | None:
    """Return a connect-success payload when this Gateway MCP is already open."""
    entry = getattr(session, "mcp_sessions", {}).get(ui_name)
    if entry is None:
        return None
    client = _mcp_client_from_entry(entry)
    if client is None or not hasattr(client, "list_tools"):
        return None
    try:
        tool_list = await asyncio.wait_for(client.list_tools(), timeout=LIST_TOOLS_TIMEOUT)
    except Exception:  # noqa: BLE001 - stale session; caller reconnects
        return None

    from chainlit.config import config
    from chainlit.logger import logger

    if config.code.on_mcp_connect:
        try:
            await config.code.on_mcp_connect(
                SimpleNamespace(name=ui_name),
                _CachedToolClient(tool_list),
            )
        except Exception:  # noqa: BLE001 - keep reuse; caller already has a live session
            logger.debug("on_mcp_connect reuse hook failed for %s", ui_name, exc_info=True)

    return {
        "success": True,
        "mcp": {
            "name": ui_name,
            "tools": [{"name": t.name} for t in tool_list.tools],
            "isUserProvided": False,
            "type": GATEWAY_MCP_TYPE,
            "url": gateway_display_url(gateway_url),
            "status": GATEWAY_MCP_STATUS_CONNECTED,
        },
    }


async def access_token_for_gateway_session(
    session: Any,
    token_manager: AccessTokenSource,
    *,
    force_refresh: bool = False,
) -> str | None:
    """Resolve JWT by session id; bind keycloak_sub if the websocket id is not mapped yet."""
    token = await token_manager.get_access_token(session.id, force_refresh=force_refresh)
    if token:
        return token
    user = getattr(session, "user", None)
    subject = (getattr(user, "metadata", None) or {}).get("keycloak_sub")
    bind = getattr(token_manager, "bind_session", None)
    if not subject or not callable(bind):
        return None
    await bind(str(subject), session.id)
    return await token_manager.get_access_token(session.id, force_refresh=force_refresh)


def gateway_mcp_auth_response(detail: str = "Unauthorized") -> JSONResponse:
    """Reject Gateway MCP HTTP without 401 — Chainlit treats 401 as logout."""
    return JSONResponse(status_code=403, content={"detail": detail})


def gateway_cookie_token(request: Any) -> str | None:
    """Read Chainlit JWT from request cookies. Do not pass Request to Mapping.get."""
    from chainlit.auth.cookie import get_token_from_cookies

    return get_token_from_cookies(getattr(request, "cookies", {}) or {})


def bind_gateway_request_user(session: Any, current_user: Any) -> bool:
    """Attach the cookie user to the websocket session. False on identifier mismatch."""
    if current_user is None:
        return True
    if getattr(session, "user", None) is None:
        session.user = current_user
        return True
    if getattr(session.user, "identifier", None) != getattr(current_user, "identifier", None):
        return False
    incoming = (getattr(current_user, "metadata", None) or {}).get("keycloak_sub")
    if incoming:
        metadata = getattr(session.user, "metadata", None)
        if metadata is None:
            session.user.metadata = {"keycloak_sub": incoming}
        elif not metadata.get("keycloak_sub"):
            metadata["keycloak_sub"] = incoming
    return True


async def connect_gateway_mcp(
    session: Any,
    ui_name: str,
    *,
    name_to_id: dict[str, str],
    token_manager: AccessTokenSource,
    gateway_client: MCPGatewayClient,
    force_refresh: bool = False,
    name_to_gateway_url: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Open a Chainlit MCP session to a Gateway server with server-side JWT injection."""
    async with _connect_lock(str(session.id), ui_name):
        return await _connect_gateway_mcp(
            session,
            ui_name,
            name_to_id=name_to_id,
            token_manager=token_manager,
            gateway_client=gateway_client,
            force_refresh=force_refresh,
            name_to_gateway_url=name_to_gateway_url,
        )


async def _connect_gateway_mcp(
    session: Any,
    ui_name: str,
    *,
    name_to_id: dict[str, str],
    token_manager: AccessTokenSource,
    gateway_client: MCPGatewayClient,
    force_refresh: bool = False,
    name_to_gateway_url: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Open a Chainlit MCP session to a Gateway server with server-side JWT injection."""
    from chainlit.config import config
    from chainlit.logger import logger
    from chainlit.mcp import (
        _MCP_CONNECT_TIMEOUT_HTTP,
        HttpMcpConnection,
        McpDestinationError,
        make_mcp_http_client_factory,
    )
    from chainlit.session import McpSession, stop_mcp_task
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    server_id = name_to_id.get(ui_name)
    if not server_id:
        raise HTTPException(status_code=404, detail="UNKNOWN_GATEWAY_MCP")

    if not force_refresh:
        existing = await existing_gateway_mcp_result(
            session,
            ui_name,
            gateway_url=(name_to_gateway_url or {}).get(ui_name),
        )
        if existing is not None:
            return existing

    token = await access_token_for_gateway_session(
        session, token_manager, force_refresh=force_refresh
    )
    if not token:
        # 401 would trigger Chainlit's API on401 → /login redirect loop.
        raise HTTPException(status_code=403, detail="Not authenticated for MCP tools")

    gateway_url = await resolve_gateway_url(gateway_client, server_id, token)
    if not gateway_url:
        raise HTTPException(status_code=403, detail="Gateway MCP not authorized")

    headers = {"Authorization": f"Bearer {token}"}
    mcp_connection = HttpMcpConnection(
        name=ui_name,
        url=gateway_url,
        headers=headers,
    )

    ready_event = asyncio.Event()
    stop_event = asyncio.Event()
    result_holder: dict[str, Any] = {}

    def _record_blocked(exc: McpDestinationError) -> None:
        result_holder["error"] = exc

    mcp_http_client_factory = make_mcp_http_client_factory(
        _gateway_destination_checker(gateway_url),
        on_blocked=_record_blocked,
    )

    async def _mcp_session_runner() -> None:
        exit_stack = AsyncExitStack()
        try:
            try:
                transport = await exit_stack.enter_async_context(
                    streamablehttp_client(
                        url=mcp_connection.url,
                        headers=mcp_connection.headers,
                        httpx_client_factory=mcp_http_client_factory,
                    )
                )
                read, write = transport[:2]
                mcp_client: ClientSession = await exit_stack.enter_async_context(
                    ClientSession(
                        read_stream=read,
                        write_stream=write,
                        sampling_callback=None,
                    )
                )
                await mcp_client.initialize()
                result_holder["client"] = mcp_client
            except BaseException as exc:  # noqa: BLE001 - mirror Chainlit connect_mcp runner
                if "error" not in result_holder:
                    result_holder["error"] = exc
                return
            finally:
                ready_event.set()

            try:
                await stop_event.wait()
            except asyncio.CancelledError:
                logger.debug("Gateway MCP background task for %r cancelled", ui_name)
        finally:
            try:
                await exit_stack.aclose()
            except BaseException:  # noqa: BLE001 - mirror Chainlit connect_mcp runner
                logger.debug(
                    "Error closing Gateway MCP exit stack for %r",
                    ui_name,
                    exc_info=True,
                )

    task = asyncio.create_task(
        _mcp_session_runner(), name=f"gateway-mcp-session-{ui_name}"
    )

    try:
        await asyncio.wait_for(ready_event.wait(), timeout=_MCP_CONNECT_TIMEOUT_HTTP)
    except TimeoutError:
        pass

    if "error" not in result_holder and "client" not in result_holder:
        result_holder["error"] = TimeoutError(
            f"Timed out after {_MCP_CONNECT_TIMEOUT_HTTP:.0f}s waiting for Gateway MCP."
        )

    if "error" in result_holder:
        await stop_mcp_task(task, stop_event, ui_name)
        connect_error = result_holder["error"]
        logger.error(
            "Failed to connect Gateway MCP %r",
            ui_name,
            exc_info=connect_error if isinstance(connect_error, BaseException) else None,
        )
        raise HTTPException(
            status_code=400,
            detail="Could not connect to the Gateway MCP server.",
        ) from (
            connect_error if isinstance(connect_error, BaseException) else None
        )

    mcp_client_session = cast("ClientSession", result_holder["client"])

    if config.code.on_mcp_connect:
        try:
            await config.code.on_mcp_connect(mcp_connection, mcp_client_session)
        except Exception as exc:
            await stop_mcp_task(task, stop_event, ui_name)
            logger.error(
                "on_mcp_connect callback failed for Gateway MCP %r",
                ui_name,
                exc_info=exc,
            )
            raise HTTPException(
                status_code=400,
                detail="Could not connect to the Gateway MCP server.",
            ) from exc

    mcp_session_obj = McpSession(
        name=mcp_connection.name,
        client=mcp_client_session,
        task=task,
        stop_event=stop_event,
    )
    old_mcp = session.swap_mcp_session(mcp_connection.name, mcp_session_obj)
    if old_mcp is not None:
        if on_mcp_disconnect := config.code.on_mcp_disconnect:
            try:
                await on_mcp_disconnect(ui_name, old_mcp.client)
            except Exception:  # noqa: BLE001 - disconnect callback must not block swap
                logger.debug(
                    "Error in on_mcp_disconnect callback for %s",
                    ui_name,
                    exc_info=True,
                )
        try:
            await old_mcp.close()
        except Exception:  # noqa: BLE001 - close errors must not block connect response
            logger.debug("Error closing old Gateway MCP session %s", ui_name, exc_info=True)

    tool_list = await mcp_client_session.list_tools()
    return {
        "success": True,
        "mcp": {
            "name": mcp_connection.name,
            "tools": [{"name": t.name} for t in tool_list.tools],
            "isUserProvided": False,
            "type": GATEWAY_MCP_TYPE,
            "url": gateway_display_url(gateway_url),
            "status": GATEWAY_MCP_STATUS_CONNECTED,
        },
    }


async def disconnect_gateway_mcp(session: Any, ui_name: str) -> dict[str, bool]:
    from chainlit.config import config

    callback = config.code.on_mcp_disconnect
    if ui_name in session.mcp_sessions:
        mcp_session_obj = session.mcp_sessions.pop(ui_name)
        try:
            if callback:
                await callback(ui_name, mcp_session_obj.client)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Could not disconnect from the MCP: {exc!s}",
            ) from exc
        finally:
            await mcp_session_obj.close()
    return {"success": True}


async def reconnect_gateway_mcp(
    session: Any,
    ui_name: str,
    *,
    name_to_id: dict[str, str],
    token_manager: AccessTokenSource,
    gateway_client: MCPGatewayClient,
    name_to_gateway_url: dict[str, str] | None = None,
) -> None:
    if ui_name in session.mcp_sessions:
        await disconnect_gateway_mcp(session, ui_name)
    await connect_gateway_mcp(
        session,
        ui_name,
        name_to_id=name_to_id,
        token_manager=token_manager,
        gateway_client=gateway_client,
        force_refresh=True,
        name_to_gateway_url=name_to_gateway_url,
    )


async def auto_connect_gateway_mcps(
    session: Any,
    *,
    name_to_id: dict[str, str],
    id_to_name: dict[str, str],
    token_manager: AccessTokenSource,
    gateway_client: MCPGatewayClient,
    name_to_gateway_url: dict[str, str] | None = None,
) -> list[str]:
    """Connect all role-allowed Gateway MCPs at chat start."""
    token = await token_manager.get_access_token(session.id)
    if not token:
        return []
    connected: list[str] = []
    for server in await gateway_client.list_servers(token):
        server_id = str(server.get("id") or "")
        ui_name = id_to_name.get(server_id)
        if not ui_name:
            continue
        try:
            await connect_gateway_mcp(
                session,
                ui_name,
                name_to_id=name_to_id,
                token_manager=token_manager,
                gateway_client=gateway_client,
                name_to_gateway_url=name_to_gateway_url,
            )
            connected.append(ui_name)
        except HTTPException:
            continue
    return connected


def _gateway_destination_checker(configured_url: str) -> Callable[[str], None]:
    expected = httpx.URL(configured_url)

    def check(url: str) -> None:
        actual = httpx.URL(url)
        if (
            actual.scheme != expected.scheme
            or actual.host != expected.host
            or _effective_port(actual) != _effective_port(expected)
        ):
            from chainlit.mcp import McpDestinationError

            raise McpDestinationError(
                f"Gateway MCP tried to reach {actual.scheme}://{actual.netloc.decode()}, "
                "which is not the configured Gateway origin."
            )

    return check


def _effective_port(parsed: httpx.URL) -> int:
    if parsed.port is not None:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def register_gateway_mcp_connect(
    app: Any,
    *,
    name_to_id: dict[str, str],
    token_manager: AccessTokenSource,
    gateway_client: MCPGatewayClient,
    name_to_gateway_url: dict[str, str] | None = None,
) -> None:
    """Install middleware and HTTP handlers for Gateway MCP connect/disconnect."""

    @app.middleware("http")
    async def gateway_mcp_middleware(request: Request, call_next: Callable[..., Any]) -> Response:
        path = request.url.path.rstrip("/")
        if path != "/mcp" or request.method not in {"POST", "DELETE"}:
            return await call_next(request)

        body = await request.body()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return await _replay_request(request, call_next, body)

        ui_name = str(payload.get("name") or "")
        if not is_gateway_mcp_name(ui_name, name_to_id):
            return await _replay_request(request, call_next, body)

        from chainlit.auth import get_current_user, require_login
        from chainlit.context import init_ws_context
        from chainlit.session import WebsocketSession

        session = WebsocketSession.get_by_id(str(payload.get("sessionId") or ""))
        if session is None:
            return JSONResponse(status_code=404, content={"detail": "Session not found"})

        init_ws_context(session)
        if require_login():
            token = gateway_cookie_token(request)
            if not token:
                return gateway_mcp_auth_response()
            try:
                current_user = await get_current_user(token)
            except HTTPException:
                return gateway_mcp_auth_response()
            if not bind_gateway_request_user(session, current_user):
                return gateway_mcp_auth_response()

        try:
            if request.method == "POST":
                result = await connect_gateway_mcp(
                    session,
                    ui_name,
                    name_to_id=name_to_id,
                    token_manager=token_manager,
                    gateway_client=gateway_client,
                    name_to_gateway_url=name_to_gateway_url,
                )
                return JSONResponse(content=result)
            result = await disconnect_gateway_mcp(session, ui_name)
            return JSONResponse(content=result)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def _replay_request(
    request: Request, call_next: Callable[..., Any], body: bytes
) -> Response:
    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    replay = Request(request.scope, receive)
    return await call_next(replay)
