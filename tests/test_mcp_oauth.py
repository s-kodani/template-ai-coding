from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastmcp.server.auth import AccessToken, AuthContext, JWTVerifier
from fastmcp.server.auth.providers.jwt import RSAKeyPair

from knowledge_mcp.auth import MCP_READER_ROLE, build_mcp_auth, require_mcp_reader
from knowledge_mcp.config import Settings

RESOURCE = "http://localhost:8000/mcp"
ISSUER = "http://localhost:8081/realms/knowledge"


def test_mcp_reader_role_is_knowledge_mcp_specific() -> None:
    assert MCP_READER_ROLE == "knowledge-mcp-reader"


def test_require_mcp_reader_allows_role() -> None:
    token = AccessToken(
        token="t",
        client_id="knowledge-mcp",
        scopes=["mcp-tools"],
        claims={"realm_access": {"roles": [MCP_READER_ROLE]}},
    )
    ctx = AuthContext(token=token, component=SimpleNamespace(name="search_knowledge"))
    assert require_mcp_reader(ctx) is True


def test_require_mcp_reader_denies_missing_role() -> None:
    token = AccessToken(
        token="t",
        client_id="knowledge-mcp",
        scopes=["mcp-tools"],
        claims={"realm_access": {"roles": []}},
    )
    ctx = AuthContext(token=token, component=SimpleNamespace(name="search_knowledge"))
    assert require_mcp_reader(ctx) is False


def test_require_mcp_reader_allows_in_process_without_token() -> None:
    ctx = AuthContext(token=None, component=SimpleNamespace(name="search_knowledge"))
    assert require_mcp_reader(ctx) is True


def test_build_mcp_auth_skips_without_jwks() -> None:
    settings = Settings(mcp_jwks_uri="")
    assert build_mcp_auth(settings) is None


def test_build_mcp_auth_uses_remote_provider_when_jwks_set() -> None:
    settings = Settings(
        mcp_jwks_uri="http://keycloak:8080/realms/knowledge/protocol/openid-connect/certs"
    )
    auth = build_mcp_auth(settings)
    assert auth is not None
    assert str(auth.authorization_servers[0]).rstrip("/") == settings.mcp_authorization_server.rstrip(
        "/"
    )


@pytest.mark.asyncio
async def test_jwt_verifier_rejects_wrong_audience() -> None:
    keys = RSAKeyPair.generate()
    verifier = JWTVerifier(
        public_key=keys.public_key,
        issuer=ISSUER,
        audience=RESOURCE,
        required_scopes=["mcp-tools"],
    )
    token = keys.create_token(
        subject="user-a",
        issuer=ISSUER,
        audience="other-mcp",
        scopes=["mcp-tools"],
        additional_claims={"azp": "chainlit", "iat": int(time.time())},
    )
    assert await verifier.verify_token(token) is None


@pytest.mark.asyncio
async def test_jwt_verifier_accepts_resource_audience() -> None:
    keys = RSAKeyPair.generate()
    verifier = JWTVerifier(
        public_key=keys.public_key,
        issuer=ISSUER,
        audience=RESOURCE,
        required_scopes=["mcp-tools"],
    )
    token = keys.create_token(
        subject="user-a",
        issuer=ISSUER,
        audience=RESOURCE,
        scopes=["mcp-tools"],
        additional_claims={"azp": "chainlit"},
    )
    access = await verifier.verify_token(token)
    assert access is not None
    assert access.client_id == "user-a" or access.claims.get("sub") == "user-a"
