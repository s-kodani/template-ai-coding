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


def _rpc(method: str, params: dict | None = None, rpc_id: int = 1) -> dict:
    body: dict[str, object] = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        body["params"] = params
    return body


def test_rest_tool_routes_are_removed(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    token = _token(private_key)
    listed = client.get(
        "/v1/mcp/knowledge/tools",
        headers={"Authorization": f"Bearer {token}"},
    )
    called = client.post(
        "/v1/mcp/knowledge/tools/search_knowledge:call",
        headers={"Authorization": f"Bearer {token}"},
        json={"arguments": {"query": "x"}},
    )
    assert listed.status_code == 404
    assert called.status_code == 404


def test_mcp_requires_chainlit_token(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.post("/mcp/knowledge", json=_rpc("tools/list"))
    assert response.status_code == 401


def test_mcp_unknown_server_is_not_found(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.post(
        "/mcp/snowflake",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("tools/list"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "MCP_SERVER_NOT_FOUND"


def test_mcp_initialize_returns_server_info(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        ),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["protocolVersion"] == "2025-11-25"
    assert payload["result"]["serverInfo"]["name"] == "mcp-gateway"


def test_mcp_tools_list_filters_allowed_and_exchanges_token(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def fake_lister(**kwargs: object) -> list[dict[str, object]]:
        seen.update(kwargs)
        return [
            {
                "name": "search_knowledge",
                "description": "Search",
                "inputSchema": {"type": "object"},
            },
            {"name": "hidden", "description": "nope", "inputSchema": {}},
        ]

    async def fake_exchange(**kwargs: object) -> dict[str, object]:
        seen["subject_token"] = kwargs["subject_token"]
        mcp_token = _token(private_key, aud=[RESOURCE], azp="mcp-gateway")
        return {"access_token": mcp_token, "expires_in": 300}

    monkeypatch.setattr("mcp_gateway.app.exchange_token", fake_exchange)
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key, tool_lister=fake_lister)
    client = TestClient(app)
    token = _token(private_key)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json=_rpc("tools/list"),
    )
    assert response.status_code == 200, response.text
    tools = response.json()["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["search_knowledge"]
    assert seen["subject_token"] == token
    assert seen["url"] == "http://mcp-server:8000/mcp"


def test_mcp_tools_call_uses_jwt_not_params_user(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def fake_caller(**kwargs: object) -> dict[str, str]:
        seen.update(kwargs)
        return {"ok": True}

    async def fake_exchange(**kwargs: object) -> dict[str, object]:
        seen["subject_token"] = kwargs["subject_token"]
        mcp_token = _token(private_key, aud=[RESOURCE], azp="mcp-gateway")
        return {"access_token": mcp_token, "expires_in": 300}

    monkeypatch.setattr("mcp_gateway.app.exchange_token", fake_exchange)
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key, tool_caller=fake_caller)
    client = TestClient(app)
    token = _token(private_key)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json=_rpc(
            "tools/call",
            {
                "name": "search_knowledge",
                "arguments": {"query": "docs", "user_id": "administrator"},
            },
        ),
    )
    assert response.status_code == 200, response.text
    content = response.json()["result"]["content"]
    assert content[0]["text"] == '{"ok": true}'
    assert seen["subject_token"] == token
    assert seen["tool_name"] == "search_knowledge"
    assert seen["arguments"] == {"query": "docs", "user_id": "administrator"}
    assert seen["url"] == "http://mcp-server:8000/mcp"


def test_mcp_tools_call_forwards_client_meta(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def fake_caller(**kwargs: object) -> dict[str, str]:
        seen["meta"] = kwargs.get("meta")
        return {"ok": True}

    async def fake_exchange(**kwargs: object) -> dict[str, object]:
        mcp_token = _token(private_key, aud=[RESOURCE], azp="mcp-gateway")
        return {"access_token": mcp_token, "expires_in": 300}

    monkeypatch.setattr("mcp_gateway.app.exchange_token", fake_exchange)
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key, tool_caller=fake_caller)
    client = TestClient(app)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc(
            "tools/call",
            {
                "name": "search_knowledge",
                "arguments": {"query": "docs"},
                "_meta": {"traceparent": "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"},
            },
        ),
    )
    assert response.status_code == 200, response.text
    meta = seen["meta"]
    assert isinstance(meta, dict)
    assert meta["traceparent"].startswith("00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-")


def test_mcp_tools_call_denies_missing_role(rsa_keys: tuple[object, str]) -> None:
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    token = _token(private_key, realm_access={"roles": ["default-roles-knowledge"]})
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {token}"},
        json=_rpc("tools/call", {"name": "search_knowledge", "arguments": {"query": "x"}}),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"


def _write_auth_registry(
    path: Path,
    *,
    mode: str | None = "keycloak_token_exchange",
    resource: str | None = RESOURCE,
    scopes: list[str] | None = None,
) -> None:
    auth: dict[str, object] = {}
    if mode is not None:
        auth["mode"] = mode
    if resource is not None:
        auth["resource"] = resource
    if scopes is not None:
        auth["scopes"] = scopes
    servers = {
        "other": {
            "enabled": True,
            "transport": {"type": "streamable_http", "url": "http://mcp-other:8000/mcp"},
            "authentication": auth,
            "authorization": {"allowed_tools": ["ping"]},
        }
    }
    path.write_text(yaml.safe_dump({"servers": servers}), encoding="utf-8")


def test_mcp_list_fails_closed_without_registry_resource(
    rsa_keys: tuple[object, str], tmp_path: Path
) -> None:
    registry = tmp_path / "registry.yml"
    _write_auth_registry(registry, resource=None, scopes=["mcp-tools"])
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(registry), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.post(
        "/mcp/other",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("tools/list"),
    )
    assert response.status_code == 500
    assert response.json()["code"] == "INVALID_REGISTRY"


def test_mcp_list_fails_closed_without_registry_scopes(
    rsa_keys: tuple[object, str], tmp_path: Path
) -> None:
    registry = tmp_path / "registry.yml"
    _write_auth_registry(registry, scopes=None)
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(registry), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.post(
        "/mcp/other",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("tools/list"),
    )
    assert response.status_code == 500
    assert response.json()["code"] == "INVALID_REGISTRY"


def test_mcp_list_rejects_unknown_auth_mode(
    rsa_keys: tuple[object, str], tmp_path: Path
) -> None:
    registry = tmp_path / "registry.yml"
    _write_auth_registry(registry, mode="passthrough", scopes=["mcp-tools"])
    private_key, _ = rsa_keys
    settings = Settings(registry_path=str(registry), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key)
    client = TestClient(app)
    response = client.post(
        "/mcp/other",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("tools/list"),
    )
    assert response.status_code == 500
    assert response.json()["code"] == "UNSUPPORTED_AUTH_MODE"
