from __future__ import annotations

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.server.http import create_streamable_http_app

from knowledge_mcp.auth import MCP_TOOLS_SCOPE, build_mcp_auth
from knowledge_mcp.config import Settings
from web_search_mcp.auth import WEB_SEARCH_MCP_TOOLS_SCOPE
from web_search_mcp.auth import build_mcp_auth as build_web_search_auth
from web_search_mcp.config import Settings as WebSearchSettings

KNOWLEDGE_RESOURCE = "http://localhost:8000/mcp"
WEB_SEARCH_RESOURCE = "http://localhost:8001/mcp"
ISSUER = "http://localhost:8081/realms/knowledge"


def _knowledge_auth():
    return build_mcp_auth(
        Settings(
            mcp_jwks_uri="http://keycloak:8080/realms/knowledge/protocol/openid-connect/certs",
            mcp_issuer=ISSUER,
            mcp_audience=KNOWLEDGE_RESOURCE,
            mcp_authorization_server=ISSUER,
            mcp_resource_base_url="http://localhost:8000",
        )
    )


def _web_search_auth():
    return build_web_search_auth(
        WebSearchSettings(
            mcp_jwks_uri="http://keycloak:8080/realms/knowledge/protocol/openid-connect/certs",
            mcp_issuer=ISSUER,
            mcp_audience=WEB_SEARCH_RESOURCE,
            mcp_authorization_server=ISSUER,
            mcp_resource_base_url="http://localhost:8001",
        )
    )


def _http_app(auth, *, path: str = "/mcp"):
    mcp = FastMCP("prm-test", auth=auth)

    @mcp.tool
    def ping() -> str:
        return "ok"

    return create_streamable_http_app(mcp, path, auth=auth, stateless_http=True)


@pytest.mark.asyncio
async def test_knowledge_prm_advertises_keycloak_and_mcp_tools() -> None:
    auth = _knowledge_auth()
    assert auth is not None
    transport = httpx.ASGITransport(app=_http_app(auth))
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == KNOWLEDGE_RESOURCE
    servers = [str(server).rstrip("/") for server in body["authorization_servers"]]
    assert ISSUER.rstrip("/") in servers
    assert MCP_TOOLS_SCOPE in body["scopes_supported"]


@pytest.mark.asyncio
async def test_web_search_prm_advertises_web_search_scope() -> None:
    auth = _web_search_auth()
    assert auth is not None
    transport = httpx.ASGITransport(app=_http_app(auth))
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8001") as client:
        response = await client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200
    body = response.json()
    assert body["resource"] == WEB_SEARCH_RESOURCE
    assert WEB_SEARCH_MCP_TOOLS_SCOPE in body["scopes_supported"]


@pytest.mark.asyncio
async def test_mcp_without_bearer_returns_resource_metadata_challenge() -> None:
    auth = _knowledge_auth()
    assert auth is not None
    transport = httpx.ASGITransport(app=_http_app(auth))
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})

    assert response.status_code == 401
    www = response.headers.get("www-authenticate", "")
    assert "resource_metadata=" in www
    assert "oauth-protected-resource" in www
    assert "error=" not in www
