from __future__ import annotations

from typing import Any

from fastmcp.server.auth import AuthContext, AuthProvider, JWTVerifier, RemoteAuthProvider

from knowledge_mcp.config import Settings

KNOWLEDGE_MCP_RESOURCE = "http://localhost:8000/mcp"
MCP_TOOLS_SCOPE = "mcp-tools"
MCP_READER_ROLE = "knowledge-mcp-reader"


def require_mcp_reader(ctx: AuthContext) -> bool:
    if ctx.token is None:
        return True
    return MCP_READER_ROLE in _realm_roles(ctx.token.claims)


def _realm_roles(claims: dict[str, Any] | None) -> set[str]:
    if not claims:
        return set()
    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") or []
    return {str(role) for role in roles}


def build_mcp_auth(settings: Settings) -> AuthProvider | None:
    if not settings.mcp_jwks_uri:
        return None
    verifier = JWTVerifier(
        jwks_uri=settings.mcp_jwks_uri,
        issuer=settings.mcp_issuer,
        audience=settings.mcp_audience,
        required_scopes=[MCP_TOOLS_SCOPE],
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[settings.mcp_authorization_server],
        base_url=settings.mcp_resource_base_url,
        resource_base_url=settings.mcp_resource_base_url,
        scopes_supported=[MCP_TOOLS_SCOPE],
        resource_name="knowledge-mcp",
    )
