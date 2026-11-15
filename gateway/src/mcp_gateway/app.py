from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from starlette.routing import Route

from mcp_gateway.cache import TokenCache
from mcp_gateway.config import Settings
from mcp_gateway.errors import ErrorBody, GatewayError
from mcp_gateway.jwt_auth import verify_chat_token, verify_exchanged_token
from mcp_gateway.mcp_client import (
    attach_trace_from_headers,
    call_mcp_tool,
    detach_trace,
    list_mcp_resources,
    list_mcp_tools,
    read_mcp_resource,
)
from mcp_gateway.mcp_http import create_mcp_app, guarded_app
from mcp_gateway.registry import get_server, list_enabled_servers, load_registry
from mcp_gateway.token_exchange import exchange_token


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise GatewayError(401, "INVALID_TOKEN", "Access token is invalid")
    return authorization.removeprefix("Bearer ").strip()


def _server_authentication(server: dict[str, Any]) -> dict[str, Any]:
    auth = server.get("authentication") or {}
    if auth.get("mode") != "keycloak_token_exchange":
        raise GatewayError(
            500,
            "UNSUPPORTED_AUTH_MODE",
            "Registry authentication.mode must be keycloak_token_exchange",
        )
    resource = auth.get("resource")
    scopes = auth.get("scopes")
    if not resource or not isinstance(scopes, list) or not scopes:
        raise GatewayError(
            500,
            "INVALID_REGISTRY",
            "Registry authentication.resource and scopes are required",
        )
    return auth


async def _mcp_token(
    *,
    settings: Settings,
    cache: TokenCache,
    source_token: str,
    server_id: str,
    server: dict[str, Any],
    signing_key: Any | None,
) -> str:
    auth = _server_authentication(server)
    scopes = [str(scope) for scope in auth["scopes"]]
    cached = cache.get(source_token, server_id, scopes)
    if cached:
        return cached
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
        expected_audience=str(auth["resource"]),
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
    tool_lister: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    resource_lister: Callable[..., Awaitable[dict[str, Any]]] | None = None,
    resource_reader: Callable[..., Awaitable[dict[str, Any]]] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    registry = load_registry(settings.registry_path, public_base_url=settings.public_base_url)
    cache = TokenCache(settings.token_cache_ttl_seconds)
    caller = tool_caller or call_mcp_tool
    lister = tool_lister or list_mcp_tools
    resource_list = resource_lister or list_mcp_resources
    resource_read = resource_reader or read_mcp_resource
    async def token_for(principal, server_id, server):
        return await _mcp_token(
            settings=settings, cache=cache, source_token=principal.token,
            server_id=server_id, server=server, signing_key=jwt_signing_key,
        )

    mcp_apps = {
        server_id: create_mcp_app(
            server_id=server_id, server=server, settings=settings, token_for=token_for,
            lister=lister, caller=caller, resource_lister=resource_list, resource_reader=resource_read,
        )
        for server_id, server in registry.items() if server.get("enabled", True)
    }

    guarded_apps = {key: guarded_app(value, settings) for key, value in mcp_apps.items()}

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for sdk_app in mcp_apps.values():
                await stack.enter_async_context(sdk_app.router.lifespan_context(sdk_app))
            yield

    app = FastAPI(title="mcp-gateway", lifespan=lifespan)

    @app.exception_handler(GatewayError)
    async def handle_gateway_error(_request: Request, exc: GatewayError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorBody(code=exc.code, message=exc.message).model_dump(),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/mcp")
    async def list_servers(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token = _bearer(authorization)
        principal = verify_chat_token(
            token,
            issuer=settings.keycloak_issuer,
            jwks_uri=settings.keycloak_jwks_uri,
            audience=settings.gateway_audience,
            azp=settings.gateway_azp,
            signing_key=jwt_signing_key,
        )
        return {"servers": list_enabled_servers(
            registry, principal.roles, public_base_url=settings.public_base_url
        )}

    class MCPEndpoint:
        async def __call__(self, scope, receive, send):
            request = Request(scope, receive)
            trace_token = attach_trace_from_headers(dict(request.headers))
            try:
                token = _bearer(request.headers.get("authorization"))
                principal = verify_chat_token(
                    token, issuer=settings.keycloak_issuer, jwks_uri=settings.keycloak_jwks_uri,
                    audience=settings.gateway_audience, azp=settings.gateway_azp,
                    signing_key=jwt_signing_key,
                )
                server_id = scope["path_params"]["server_id"]
                get_server(registry, server_id)
                request.state.principal = principal
                await guarded_apps[server_id](scope, receive, send)
            except GatewayError as exc:
                # Authentication/endpoint errors occur before JSON-RPC dispatch.
                response = JSONResponse(status_code=exc.status_code, content={
                    "jsonrpc": "2.0", "id": None,
                    "error": {"code": -32000, "message": exc.message,
                              "data": {"code": exc.code, "status": exc.status_code}},
                })
                await response(scope, receive, send)
            finally:
                detach_trace(trace_token)

    # Delegate the exact existing URL to the SDK; mounting would add a slash redirect.
    app.router.routes.append(Route("/mcp/{server_id}", MCPEndpoint()))
    return app
