from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from mcp_gateway.cache import TokenCache
from mcp_gateway.config import Settings
from mcp_gateway.errors import ErrorBody, GatewayError, ToolCallBody
from mcp_gateway.jwt_auth import verify_chainlit_token, verify_exchanged_token
from mcp_gateway.mcp_client import (
    attach_trace_from_headers,
    call_mcp_tool,
    detach_trace,
    list_mcp_tools,
)
from mcp_gateway.policy import authorize_tool
from mcp_gateway.registry import get_server, load_registry
from mcp_gateway.token_exchange import exchange_token


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise GatewayError(401, "INVALID_TOKEN", "Access token is invalid")
    return authorization.removeprefix("Bearer ").strip()


async def _mcp_token(
    *,
    settings: Settings,
    cache: TokenCache,
    source_token: str,
    server_id: str,
    server: dict[str, Any],
    signing_key: Any | None,
) -> str:
    scopes = list(server.get("authentication", {}).get("scopes") or ["mcp-tools"])
    cached = cache.get(source_token, server_id, scopes)
    if cached:
        return cached
    auth = server.get("authentication") or {}
    payload = await exchange_token(
        token_url=settings.keycloak_token_url,
        client_id=settings.gateway_client_id,
        client_secret=settings.gateway_client_secret,
        subject_token=source_token,
        scope=" ".join(scopes),
        timeout_seconds=settings.token_exchange_timeout_seconds,
    )
    mcp_token = str(payload["access_token"])
    verify_exchanged_token(
        mcp_token,
        issuer=settings.keycloak_issuer,
        expected_audience=auth.get("resource") or "http://localhost:8000/mcp",
        signing_key=signing_key,
        jwks_uri=settings.keycloak_jwks_uri,
    )
    exp = payload.get("expires_in")
    expires_at = __import__("time").time() + int(exp or 300)
    cache.put(source_token, server_id, scopes, mcp_token, expires_at)
    return mcp_token


def create_app(
    settings: Settings | None = None,
    *,
    jwt_signing_key: Any | None = None,
    tool_caller: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    tool_lister: Callable[..., Awaitable[list[dict[str, Any]]]] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    registry = load_registry(settings.registry_path)
    cache = TokenCache(settings.token_cache_ttl_seconds)
    caller = tool_caller or call_mcp_tool
    lister = tool_lister or list_mcp_tools
    app = FastAPI(title="mcp-gateway")

    @app.exception_handler(GatewayError)
    async def handle_gateway_error(_request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorBody(code=exc.code, message=exc.message).model_dump(),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/mcp/{server_id}/tools")
    async def list_tools(
        server_id: str,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = _bearer(authorization)
        trace_token = attach_trace_from_headers(dict(request.headers))
        try:
            principal = verify_chainlit_token(
                token,
                issuer=settings.keycloak_issuer,
                jwks_uri=settings.keycloak_jwks_uri,
                audience=settings.gateway_audience,
                azp=settings.gateway_azp,
                signing_key=jwt_signing_key,
            )
            server = get_server(registry, server_id)
            mcp_token = await _mcp_token(
                settings=settings,
                cache=cache,
                source_token=principal.token,
                server_id=server_id,
                server=server,
                signing_key=jwt_signing_key,
            )
            tools = await lister(
                url=server["transport"]["url"],
                token=mcp_token,
                timeout_seconds=float(server.get("timeout_seconds") or settings.mcp_call_timeout_seconds),
            )
            allowed = set(server.get("authorization", {}).get("allowed_tools") or [])
            return {"tools": [tool for tool in tools if tool.get("name") in allowed]}
        finally:
            detach_trace(trace_token)

    @app.post("/v1/mcp/{server_id}/tools/{tool_name}:call")
    async def call_tool(
        server_id: str,
        tool_name: str,
        body: ToolCallBody,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = _bearer(authorization)
        trace_token = attach_trace_from_headers(dict(request.headers))
        try:
            principal = verify_chainlit_token(
                token,
                issuer=settings.keycloak_issuer,
                jwks_uri=settings.keycloak_jwks_uri,
                audience=settings.gateway_audience,
                azp=settings.gateway_azp,
                signing_key=jwt_signing_key,
            )
            server = get_server(registry, server_id)
            authorize_tool(principal, server, tool_name)
            mcp_token = await _mcp_token(
                settings=settings,
                cache=cache,
                source_token=principal.token,
                server_id=server_id,
                server=server,
                signing_key=jwt_signing_key,
            )
            return await caller(
                url=server["transport"]["url"],
                token=mcp_token,
                tool_name=tool_name,
                arguments=body.arguments,
                timeout_seconds=float(server.get("timeout_seconds") or settings.mcp_call_timeout_seconds),
            )
        finally:
            detach_trace(trace_token)

    return app
