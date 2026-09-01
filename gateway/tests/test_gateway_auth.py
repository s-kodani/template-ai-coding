from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from mcp_gateway.app import create_app
from mcp_gateway.config import Settings
from mcp_gateway.jwt_auth import verify_chainlit_token, verify_exchanged_token
from mcp_gateway.policy import authorize_tool
from mcp_gateway.principal import Principal
from mcp_gateway.token_exchange import exchange_token

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
        "realm_access": {"roles": ["knowledge-mcp-reader"]},
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


def test_registry_does_not_use_client_id_as_exchange_audience() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    auth = registry["servers"]["knowledge"]["authentication"]
    assert "target_client" not in auth
    assert auth["resource"] == RESOURCE
    assert auth["scopes"] == ["mcp-tools"]
    assert registry["servers"]["knowledge"]["authorization"]["required_roles"] == [
        "knowledge-mcp-reader"
    ]


async def test_exchange_token_omits_audience_for_keycloak_v2() -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"access_token": "mcp-token"}

    class FakeClient:
        async def post(self, _url: str, data: dict[str, str]) -> FakeResponse:
            captured["data"] = data
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    payload = await exchange_token(
        token_url="http://keycloak/token",
        client_id="mcp-gateway",
        client_secret="secret",
        subject_token="chainlit-token",
        scope="mcp-tools",
        timeout_seconds=5,
        client=FakeClient(),  # type: ignore[arg-type]
    )
    assert payload["access_token"] == "mcp-token"
    data = captured["data"]
    assert isinstance(data, dict)
    assert "audience" not in data
    assert data["scope"] == "mcp-tools"
    assert data["subject_token"] == "chainlit-token"


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


def test_list_servers_requires_chainlit_token(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.get("/v1/mcp")
    assert response.status_code == 401


def _write_role_registry(path: Path) -> None:
    path.write_text(
        """
servers:
  knowledge:
    enabled: true
    ui:
      name: knowledge-mcp
    authorization:
      allowed_tools:
        - search_knowledge
        - get_document
      required_roles:
        - knowledge-mcp-reader
  other:
    enabled: true
    authorization:
      allowed_tools:
        - ping
  off:
    enabled: false
    authorization:
      allowed_tools:
        - hidden
      required_roles:
        - mcp-reader
""",
        encoding="utf-8",
    )


def test_list_servers_returns_enabled_registry_entries(
    rsa_keys: tuple[object, str], tmp_path: Path
) -> None:
    registry = tmp_path / "registry.yml"
    _write_role_registry(registry)
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(registry), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.get("/v1/mcp", headers={"Authorization": f"Bearer {_token(private_key)}"})
    assert response.status_code == 200
    assert response.json() == {
        "servers": [
            {
                "id": "knowledge",
                "name": "knowledge-mcp",
                "tools": ["search_knowledge", "get_document"],
                "url": "http://mcp-gateway:8082/mcp/knowledge",
            },
            {
                "id": "other",
                "name": "other",
                "tools": ["ping"],
                "url": "http://mcp-gateway:8082/mcp/other",
            },
        ]
    }


def test_list_servers_hides_servers_missing_required_roles(
    rsa_keys: tuple[object, str], tmp_path: Path
) -> None:
    registry = tmp_path / "registry.yml"
    _write_role_registry(registry)
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(registry), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    token = _token(private_key, realm_access={"roles": ["default-roles-knowledge"]})
    response = client.get("/v1/mcp", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {
        "servers": [
            {
                "id": "other",
                "name": "other",
                "tools": ["ping"],
                "url": "http://mcp-gateway:8082/mcp/other",
            }
        ]
    }


def test_list_servers_uses_public_base_url(
    rsa_keys: tuple[object, str], tmp_path: Path
) -> None:
    registry = tmp_path / "registry.yml"
    _write_role_registry(registry)
    private_key, _ = rsa_keys
    settings = Settings(
        registry_path=str(registry),
        keycloak_issuer=ISSUER,
        public_base_url="http://gw.internal:9",
    )
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.get("/v1/mcp", headers={"Authorization": f"Bearer {_token(private_key)}"})
    assert response.status_code == 200
    urls = {item["id"]: item["url"] for item in response.json()["servers"]}
    assert urls["knowledge"] == "http://gw.internal:9/mcp/knowledge"
