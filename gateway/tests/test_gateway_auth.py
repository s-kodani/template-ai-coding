from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from mcp_gateway.app import create_app
from mcp_gateway.config import Settings
from mcp_gateway.jwt_auth import verify_chainlit_token, verify_exchanged_token
from mcp_gateway.policy import authorize_tool
from mcp_gateway.principal import Principal

ISSUER = "http://localhost:8081/realms/knowledge"
RESOURCE = "http://localhost:8000/mcp"
REGISTRY = Path(__file__).resolve().parents[2] / "infra" / "app" / "gateway-registry.yml"


@pytest.fixture
def rsa_keys() -> tuple[object, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key, private_pem.decode()


def _token(private_key: object, **claims: object) -> str:
    payload = {
        "iss": ISSUER,
        "sub": "user-1",
        "azp": "chainlit",
        "aud": ["chainlit", "mcp-gateway"],
        "exp": int(time.time()) + 3600,
        "nbf": int(time.time()) - 5,
        "realm_access": {"roles": ["mcp-reader"]},
        "scope": "openid profile email",
        **claims,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_verify_rejects_missing_gateway_audience(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    token = _token(private_key, aud=["chainlit"])
    with pytest.raises(Exception) as exc:
        verify_chainlit_token(
            token,
            issuer=ISSUER,
            jwks_uri="",
            audience="mcp-gateway",
            azp="chainlit",
            signing_key=private_key,
        )
    assert exc.value.code == "INVALID_AUDIENCE"  # type: ignore[attr-defined]


def test_verify_rejects_wrong_azp(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    token = _token(private_key, azp="other-client")
    with pytest.raises(Exception) as exc:
        verify_chainlit_token(
            token,
            issuer=ISSUER,
            jwks_uri="",
            audience="mcp-gateway",
            azp="chainlit",
            signing_key=private_key,
        )
    assert exc.value.code == "INVALID_AUDIENCE"  # type: ignore[attr-defined]


def test_verify_rejects_expired(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    token = _token(private_key, exp=int(time.time()) - 10)
    with pytest.raises(Exception) as exc:
        verify_chainlit_token(
            token,
            issuer=ISSUER,
            jwks_uri="",
            audience="mcp-gateway",
            azp="chainlit",
            signing_key=private_key,
        )
    assert exc.value.code == "TOKEN_EXPIRED"  # type: ignore[attr-defined]


def test_exchanged_token_must_include_resource_audience(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    token = _token(private_key, aud=["knowledge-mcp"])
    with pytest.raises(Exception) as exc:
        verify_exchanged_token(
            token,
            issuer=ISSUER,
            expected_audience=RESOURCE,
            signing_key=private_key,
        )
    assert exc.value.code == "TOKEN_AUDIENCE_MISMATCH"  # type: ignore[attr-defined]


def test_policy_denies_missing_role() -> None:
    principal = Principal(
        subject="user-1",
        issuer=ISSUER,
        authorized_party="chainlit",
        roles=frozenset(),
        scopes=frozenset({"mcp-tools"}),
        token="t",
    )
    server = {
        "authorization": {
            "allowed_tools": ["search_knowledge"],
            "required_roles": ["mcp-reader"],
        }
    }
    with pytest.raises(Exception) as exc:
        authorize_tool(principal, server, "search_knowledge")
    assert exc.value.code == "ACCESS_DENIED"  # type: ignore[attr-defined]


def test_call_rejects_user_id_in_body(rsa_keys: tuple[object, str], tmp_path: Path) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)

    async def fake_exchange(**_: object) -> dict[str, str]:
        raise AssertionError("exchange should not run for invalid body")

    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    token = _token(private_key)
    response = client.post(
        "/v1/mcp/knowledge/tools/search_knowledge:call",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": "administrator", "arguments": {"query": "x"}},
    )
    assert response.status_code == 422


def test_call_uses_jwt_subject_not_body(rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def fake_caller(**kwargs: object) -> dict[str, str]:
        seen.update(kwargs)
        return {"ok": True}

    async def fake_exchange(**kwargs: object) -> dict[str, object]:
        seen["subject_token"] = kwargs["subject_token"]
        mcp_token = _token(private_key, aud=[RESOURCE, "knowledge-mcp"], azp="mcp-gateway")
        return {"access_token": mcp_token, "expires_in": 300}

    monkeypatch.setattr("mcp_gateway.app.exchange_token", fake_exchange)
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key, tool_caller=fake_caller)
    client = TestClient(app)
    token = _token(private_key)
    response = client.post(
        "/v1/mcp/knowledge/tools/search_knowledge:call",
        headers={"Authorization": f"Bearer {token}"},
        json={"arguments": {"query": "docs"}},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}
    assert seen["subject_token"] == token
    assert seen["url"] == "http://mcp-server:8000/mcp"


def test_unknown_server_is_not_found(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    token = _token(private_key)
    response = client.post(
        "/v1/mcp/snowflake/tools/search_knowledge:call",
        headers={"Authorization": f"Bearer {token}"},
        json={"arguments": {}},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "MCP_SERVER_NOT_FOUND"
