"""Official SDK server boundary; downstream connections remain handshake-era clients."""

from __future__ import annotations

import json
from typing import Any

from mcp import types
from mcp.server.caching import CACHEABLE_METHODS, CacheHint
from mcp.server.lowlevel import Server
from mcp.server.transport_security import (
    DEFAULT_MAX_REQUEST_BODY_SIZE,
    RequestBodyLimitMiddleware,
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from mcp.shared.exceptions import MCPError
from mcp.shared.inbound import InboundLadderRejection, classify_inbound_request
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_gateway.errors import GatewayError
from mcp_gateway.mcp_client import _trace_meta
from mcp_gateway.policy import authorize_resource, authorize_server, authorize_tool


class GatewayServer(Server):
    def create_initialization_options(self, *args, **kwargs):
        # The 2025 wire schema carries extension advertisements under experimental.
        kwargs.setdefault("experimental_capabilities", self.extensions)
        return super().create_initialization_options(*args, **kwargs)


def forwarded_meta(meta: Any) -> dict[str, Any] | None:
    incoming = dict(meta or {})
    # Protocol envelopes terminate here. The Gateway is the downstream client.
    incoming = {k: v for k, v in incoming.items() if not k.startswith("io.modelcontextprotocol/")}
    return {**_trace_meta(), **incoming} or None


def create_mcp_app(
    *, server_id, server, settings, token_for, lister, caller, resource_lister, resource_reader
):
    async def upstream(ctx):
        principal = ctx.request.state.principal
        authorize_server(principal, server)
        return {
            "url": server["transport"]["url"],
            "token": await token_for(principal, server_id, server),
            "timeout_seconds": float(
                server.get("timeout_seconds") or settings.mcp_call_timeout_seconds
            ),
            "meta": forwarded_meta(ctx.meta),
        }

    async def list_tools(ctx, params):
        # The SDK may list schemas while validating a modern tools/call. Authorize
        # that original call before this implicit listing can exchange a token.
        request_body = await ctx.request.json()
        if request_body.get("method") == "tools/call":
            authorize_tool(ctx.request.state.principal, server, request_body["params"]["name"])
        page = await lister(**await upstream(ctx), cursor=params.cursor if params else None)
        allowed = set(server.get("authorization", {}).get("allowed_tools") or [])
        return types.ListToolsResult.model_validate(
            {
                **page,
                "tools": [tool for tool in page["tools"] if tool["name"] in allowed],
                "ttlMs": 0,
                "cacheScope": "private",
            }
        )

    async def call_tool(ctx, params):
        authorize_tool(ctx.request.state.principal, server, params.name)
        output = await caller(
            **await upstream(ctx), tool_name=params.name, arguments=params.arguments or {}
        )
        return types.CallToolResult.model_validate(output)

    async def list_resources(ctx, params):
        authorize_server(ctx.request.state.principal, server)
        allowed = set(server.get("authorization", {}).get("allowed_resources") or [])
        page = (
            await resource_lister(**await upstream(ctx), cursor=params.cursor if params else None)
            if allowed
            else {"resources": []}
        )
        return types.ListResourcesResult.model_validate(
            {
                **page,
                "resources": [r for r in page["resources"] if r["uri"] in allowed],
                "ttlMs": 0,
                "cacheScope": "private",
            }
        )

    async def read_resource(ctx, params):
        uri = str(params.uri)
        authorize_resource(ctx.request.state.principal, server, uri)
        output = await resource_reader(**await upstream(ctx), uri=uri)
        return types.ReadResourceResult.model_validate(
            {**output, "ttlMs": 0, "cacheScope": "private"}
        )

    async def ping(ctx, params):
        return types.EmptyResult()

    sdk = GatewayServer(
        "mcp-gateway",
        version="0.1.0",
        cache_hints={method: CacheHint(ttl_ms=0, scope="private") for method in CACHEABLE_METHODS},
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        on_list_resources=list_resources,
        on_read_resource=read_resource,
        on_ping=ping,
    )
    sdk.extensions["io.modelcontextprotocol/ui"] = {}

    async def gateway_errors(ctx, call_next):
        try:
            return await call_next(ctx)
        except GatewayError as exc:
            raise MCPError(
                -32000, exc.message, {"code": exc.code, "status": exc.status_code}
            ) from exc

    sdk.middleware.append(gateway_errors)
    return sdk.streamable_http_app(
        streamable_http_path=f"/mcp/{server_id}",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=settings.mcp_allowed_hosts,
            allowed_origins=settings.mcp_allowed_origins,
        ),
    )


class EnvelopeGuard:
    """Close SDK 2.3's header-only era-routing gap using its own validator."""

    def __init__(self, app, security):
        self.app = app
        self.security = TransportSecurityMiddleware(security)

    async def __call__(self, scope, receive, send):
        request = Request(scope, receive)
        rejection = await self.security.validate_request(request, is_post=request.method == "POST")
        if rejection is not None:
            return await rejection(scope, receive, send)
        if request.method != "POST" or request.headers.get("mcp-protocol-version") == "2026-07-28":
            return await self.app(scope, receive, send)
        raw = await request.body()
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError, RecursionError):
            body = None  # Let the SDK report malformed messages.
        params = body.get("params") if isinstance(body, dict) else None
        meta = params.get("_meta") if isinstance(params, dict) else None
        if isinstance(meta, dict) and "io.modelcontextprotocol/protocolVersion" in meta:
            verdict = classify_inbound_request(body, headers=dict(request.headers))
            if isinstance(verdict, InboundLadderRejection):
                rpc_id = body.get("id")
                if type(rpc_id) not in (str, int):
                    rpc_id = None
                error = types.JSONRPCError(
                    jsonrpc="2.0",
                    id=rpc_id,
                    error=types.ErrorData(
                        code=verdict.code,
                        message=verdict.message,
                        data=verdict.data,
                    ),
                )
                return await JSONResponse(
                    error.model_dump(by_alias=True, exclude_none=True), status_code=400
                )(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def guarded_app(app, settings):
    security = TransportSecuritySettings(
        allowed_hosts=settings.mcp_allowed_hosts, allowed_origins=settings.mcp_allowed_origins,
    )
    return RequestBodyLimitMiddleware(EnvelopeGuard(app, security), DEFAULT_MAX_REQUEST_BODY_SIZE)
