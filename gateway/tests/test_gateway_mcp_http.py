from __future__ import annotations

import sys
import time
from contextlib import ExitStack
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
WEB_SEARCH_RESOURCE = "http://localhost:8001/mcp"
REGISTRY = Path(__file__).resolve().parents[2] / "infra" / "app" / "gateway-registry.yml"


@pytest.fixture(autouse=True)
def http_clients(monkeypatch):
    """Run the ASGI lifespan and use the required transport headers in wire tests."""
    original = TestClient
    with ExitStack() as stack:
        def started_client(app):
            return stack.enter_context(original(app, base_url="http://mcp-gateway:8082", headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            }))
        monkeypatch.setattr(sys.modules[__name__], "TestClient", started_client)
        yield


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
        "azp": "open-webui",
        "aud": ["open-webui", "mcp-gateway"],
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
    assert response.json()["error"]["data"]["code"] == "MCP_SERVER_NOT_FOUND"


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

    async def fake_lister(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {"tools": [
            {
                "name": "search_knowledge",
                "description": "Search",
                "inputSchema": {"type": "object"},
            },
            {"name": "hidden", "description": "nope", "inputSchema": {}},
        ]}

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
        return {"content": [{"type": "text", "text": '{"ok": true}'}], "isError": False}

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
        return {"content": [{"type": "text", "text": '{"ok": true}'}], "isError": False}

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


def test_mcp_tools_call_web_search_exchanges_scope_and_forwards_call(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def fake_caller(**kwargs: object) -> dict[str, str]:
        seen.update(kwargs)
        return {
            "content": [{"type": "text", "text": '{"query": "news", "results": []}'}],
            "structuredContent": {"query": "news", "results": []},
            "isError": False,
        }

    async def fake_exchange(**kwargs: object) -> dict[str, object]:
        seen["exchange_scope"] = kwargs["scope"]
        seen["subject_token"] = kwargs["subject_token"]
        mcp_token = _token(
            private_key,
            aud=[WEB_SEARCH_RESOURCE],
            azp="mcp-gateway",
            scope="web-search-mcp-tools",
        )
        return {"access_token": mcp_token, "expires_in": 300}

    monkeypatch.setattr("mcp_gateway.app.exchange_token", fake_exchange)
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    app = create_app(settings, jwt_signing_key=private_key, tool_caller=fake_caller)
    client = TestClient(app)
    token = _token(
        private_key,
        realm_access={"roles": ["web-search-reader", "default-roles-knowledge"]},
    )
    response = client.post(
        "/mcp/web-search",
        headers={"Authorization": f"Bearer {token}"},
        json=_rpc(
            "tools/call",
            {"name": "search_web", "arguments": {"query": "news", "count": 3}},
        ),
    )
    assert response.status_code == 200, response.text
    content = response.json()["result"]["content"]
    assert '"query": "news"' in content[0]["text"]
    assert seen["exchange_scope"] == "web-search-mcp-tools"
    assert seen["subject_token"] == token
    assert seen["tool_name"] == "search_web"
    assert seen["arguments"] == {"query": "news", "count": 3}
    assert seen["url"] == "http://web-search-mcp:8001/mcp"


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
    assert response.status_code == 200
    assert response.json()["error"]["data"]["status"] == 403
    assert response.json()["error"]["data"]["code"] == "ACCESS_DENIED"


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
    assert response.status_code == 200
    assert response.json()["error"]["data"]["status"] == 500
    assert response.json()["error"]["data"]["code"] == "INVALID_REGISTRY"


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
    assert response.status_code == 200
    assert response.json()["error"]["data"]["status"] == 500
    assert response.json()["error"]["data"]["code"] == "INVALID_REGISTRY"


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
    assert response.status_code == 200
    assert response.json()["error"]["data"]["status"] == 500
    assert response.json()["error"]["data"]["code"] == "UNSUPPORTED_AUTH_MODE"


UI_URI = "ui://knowledge/search-results.html"


def _apps_client(
    private_key: object,
    monkeypatch: pytest.MonkeyPatch,
    *,
    seen: dict[str, object],
    **adapters: object,
) -> TestClient:
    async def fake_exchange(**kwargs: object) -> dict[str, object]:
        seen["exchange_scope"] = kwargs["scope"]
        seen["subject_token"] = kwargs["subject_token"]
        return {
            "access_token": _token(private_key, aud=[RESOURCE], azp="mcp-gateway"),
            "expires_in": 300,
        }

    monkeypatch.setattr("mcp_gateway.app.exchange_token", fake_exchange)
    settings = Settings(registry_path=str(REGISTRY), keycloak_issuer=ISSUER)
    return TestClient(create_app(settings, jwt_signing_key=private_key, **adapters))


def test_mcp_initialize_negotiates_supported_version_and_resources(
    rsa_keys: tuple[object, str],
) -> None:
    private_key, _ = rsa_keys
    app = create_app(Settings(registry_path=str(REGISTRY)), jwt_signing_key=private_key)
    response = TestClient(app).post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("initialize", {"protocolVersion": "2099-01-01", "capabilities": {},
                                 "clientInfo": {"name": "test", "version": "0"}}),
    )
    result = response.json()["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert result["capabilities"]["resources"] == {"listChanged": False, "subscribe": False}
    assert result["capabilities"]["experimental"]["io.modelcontextprotocol/ui"] == {}


def test_mcp_tools_list_keeps_apps_metadata_and_pagination(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def lister(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "tools": [{
                "name": "search_knowledge",
                "description": "Search",
                "inputSchema": {"type": "object"},
                "outputSchema": {"type": "object", "properties": {"hits": {"type": "array"}}},
                "annotations": {"readOnlyHint": True},
                "_meta": {"ui": {"resourceUri": UI_URI}},
            }],
            "nextCursor": "page-2",
            "_meta": {"page": {"source": "knowledge"}},
        }

    client = _apps_client(private_key, monkeypatch, seen=seen, tool_lister=lister)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("tools/list", {"cursor": "page-1"}),
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["tools"][0]["_meta"]["ui"]["resourceUri"] == UI_URI
    assert result["tools"][0]["annotations"]["readOnlyHint"] is True
    assert result["tools"][0]["outputSchema"]["properties"]["hits"]["type"] == "array"
    assert result["nextCursor"] == "page-2"
    assert result["_meta"] == {"page": {"source": "knowledge"}}
    assert seen["cursor"] == "page-1"


def test_mcp_tools_call_keeps_original_result_and_nested_meta(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def caller(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "content": [{"type": "text", "text": "Search failed"}, {"type": "text", "text": "Retry"}],
            "structuredContent": {"error": "unavailable"},
            "isError": True,
            "_meta": {"ui": {"resourceUri": UI_URI}},
        }

    client = _apps_client(private_key, monkeypatch, seen=seen, tool_caller=caller)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("tools/call", {
            "name": "search_knowledge", "arguments": {"query": "x"},
            "_meta": {"ui": {"pagination": {"page": 2}}, "baggage": "user=1"},
        }),
    )
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["isError"] is True
    assert result["content"] == [
        {"type": "text", "text": "Search failed"}, {"type": "text", "text": "Retry"},
    ]
    assert result["structuredContent"] == {"error": "unavailable"}
    assert result["_meta"] == {"ui": {"resourceUri": UI_URI}}
    assert seen["meta"] == {"ui": {"pagination": {"page": 2}}, "baggage": "user=1"}


def test_mcp_resources_read_preserves_html_csp_and_uses_exchange(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def reader(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {"contents": [{
            "uri": UI_URI, "mimeType": "text/html;profile=mcp-app", "text": "<main>Search</main>",
            "_meta": {"ui": {"csp": {"connectDomains": [], "resourceDomains": []}}},
        }]}

    client = _apps_client(private_key, monkeypatch, seen=seen, resource_reader=reader)
    source_token = _token(private_key)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {source_token}"},
        json=_rpc("resources/read", {"uri": UI_URI, "_meta": {"ui": {"view": "results"}}}),
    )
    assert response.status_code == 200, response.text
    content = response.json()["result"]["contents"][0]
    assert content["mimeType"] == "text/html;profile=mcp-app"
    assert content["text"] == "<main>Search</main>"
    assert content["_meta"]["ui"]["csp"] == {"connectDomains": [], "resourceDomains": []}
    assert seen["subject_token"] == source_token
    assert seen["token"] != source_token
    assert seen["uri"] == UI_URI
    assert seen["meta"] == {"ui": {"view": "results"}}


def test_mcp_resources_list_filters_exact_uris_and_preserves_empty_page_cursor(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}

    async def lister(**kwargs: object) -> dict[str, object]:
        seen.update(kwargs)
        return {
            "resources": [{"uri": "ui://private/admin.html", "name": "Admin"}],
            "nextCursor": "next-page",
            "_meta": {"source": "upstream"},
        }

    client = _apps_client(private_key, monkeypatch, seen=seen, resource_lister=lister)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("resources/list", {"cursor": "current-page"}),
    )
    assert response.status_code == 200, response.text
    assert response.json()["result"] == {
        "resources": [], "nextCursor": "next-page", "_meta": {"source": "upstream"},
    }
    assert seen["cursor"] == "current-page"


@pytest.mark.parametrize("uri", ["ui://private/admin.html", "http://169.254.169.254/", "", UI_URI + "?x=1"])
def test_mcp_resources_read_denies_unlisted_uri_before_exchange(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch, uri: str,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key)}"},
        json=_rpc("resources/read", {"uri": uri}),
    )
    assert response.status_code == 200
    assert response.json()["error"]["data"]["status"] == 404
    assert response.json()["error"]["data"]["code"] == "RESOURCE_NOT_FOUND"
    assert "subject_token" not in seen


@pytest.mark.parametrize("method,params", [
    ("tools/list", {}),
    ("resources/list", {}),
    ("resources/read", {"uri": UI_URI}),
])
def test_mcp_lists_and_resource_read_deny_missing_role_before_exchange(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch, method: str, params: dict,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    response = client.post(
        "/mcp/knowledge",
        headers={"Authorization": f"Bearer {_token(private_key, realm_access={'roles': []})}"},
        json=_rpc(method, params),
    )
    assert response.status_code == 200
    assert response.json()["error"]["data"]["status"] == 403
    assert response.json()["error"]["data"]["code"] == "ACCESS_DENIED"
    assert "subject_token" not in seen


def test_mcp_resources_are_not_exposed_without_resource_allowlist(
    rsa_keys: tuple[object, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key, _ = rsa_keys
    seen: dict[str, object] = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    headers = {"Authorization": f"Bearer {_token(private_key, realm_access={'roles': ['web-search-reader']})}"}
    listed = client.post("/mcp/web-search", headers=headers, json=_rpc("resources/list"))
    read = client.post("/mcp/web-search", headers=headers, json=_rpc("resources/read", {"uri": UI_URI}))
    assert listed.status_code == 200
    assert listed.json()["result"] == {"resources": []}
    assert read.status_code == 200
    assert read.json()["error"]["data"]["status"] == 404
    assert "subject_token" not in seen


MODERN = "2026-07-28"


def _modern_request(method, params=None):
    params = {**(params or {})}
    params['_meta'] = {**params.get('_meta', {}),
        'io.modelcontextprotocol/protocolVersion': MODERN,
        'io.modelcontextprotocol/clientInfo': {'name': 'modern-test', 'version': '1'},
        'io.modelcontextprotocol/clientCapabilities': {},
    }
    headers = {'MCP-Protocol-Version': MODERN, 'Mcp-Method': method}
    if method == 'tools/call':
        headers['Mcp-Name'] = params['name']
    elif method == 'resources/read':
        headers['Mcp-Name'] = params['uri']
    return _rpc(method, params), headers


def test_modern_discovery_advertises_only_implemented_features(rsa_keys):
    private_key, _ = rsa_keys
    client = TestClient(create_app(Settings(registry_path=str(REGISTRY)), jwt_signing_key=private_key))
    body, headers = _modern_request('server/discover')
    response = client.post('/mcp/knowledge', json=body,
                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'})
    assert response.status_code == 200, response.text
    result = response.json()['result']
    assert result['supportedVersions'] == [MODERN]
    assert result['resultType'] == 'complete'
    assert result['_meta']['io.modelcontextprotocol/serverInfo']['name'] == 'mcp-gateway'
    assert result['capabilities']['extensions']['io.modelcontextprotocol/ui'] == {}
    assert 'tasks' not in result['capabilities']
    assert not result['capabilities']['tools'].get('listChanged')
    assert result['ttlMs'] == 0 and result['cacheScope'] == 'private'
    assert 'mcp-session-id' not in response.headers


def test_modern_direct_call_terminates_protocol_metadata_but_keeps_apps_and_trace(rsa_keys, monkeypatch):
    private_key, _ = rsa_keys
    seen = {}

    async def caller(**kwargs):
        seen.update(kwargs)
        return {'content': [{'type': 'text', 'text': 'ok'}],
                'structuredContent': {'hits': []}, '_meta': {'ui': {'resourceUri': UI_URI}}}

    client = _apps_client(private_key, monkeypatch, seen=seen, tool_caller=caller)
    body, headers = _modern_request('tools/call', {
        'name': 'search_knowledge', 'arguments': {'query': 'x'},
        '_meta': {'traceparent': '00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01',
                  'ui': {'page': 2}},
    })
    response = client.post('/mcp/knowledge', json=body,
                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'})
    assert response.status_code == 200, response.text
    result = response.json()['result']
    assert result['resultType'] == 'complete'
    assert result['structuredContent'] == {'hits': []}
    assert result['_meta']['ui']['resourceUri'] == UI_URI
    assert seen['meta']['ui'] == {'page': 2}
    assert seen['meta']['traceparent'].startswith('00-aaaa')
    assert not any(key.startswith('io.modelcontextprotocol/') for key in seen['meta'])


@pytest.mark.parametrize('changed,value', [
    ('Mcp-Method', 'resources/list'), ('Mcp-Name', 'get_document'),
    ('MCP-Protocol-Version', '2025-11-25'),
])
def test_modern_header_mismatch_is_rejected_before_exchange(rsa_keys, monkeypatch, changed, value):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    body, headers = _modern_request('tools/call', {'name': 'search_knowledge', 'arguments': {}})
    headers[changed] = value
    response = client.post('/mcp/knowledge', json=body,
                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'})
    assert response.status_code == 400, response.text
    assert 'error' in response.json()
    assert 'subject_token' not in seen


def test_modern_unknown_version_fails_before_exchange(rsa_keys, monkeypatch):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    body, headers = _modern_request('tools/list')
    headers['MCP-Protocol-Version'] = '2099-01-01'
    body['params']['_meta']['io.modelcontextprotocol/protocolVersion'] = '2099-01-01'
    response = client.post('/mcp/knowledge', json=body,
                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'})
    assert response.status_code == 400, response.text
    assert 'subject_token' not in seen


def test_invalid_origin_rejected_without_exchange(rsa_keys, monkeypatch):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    body, headers = _modern_request('server/discover')
    response = client.post('/mcp/knowledge', json=body, headers={
        **headers, 'Authorization': f'Bearer {_token(private_key)}', 'Origin': 'https://evil.example',
    })
    assert response.status_code == 403
    assert 'subject_token' not in seen


@pytest.mark.parametrize('mode,expected_version', [
    ('auto', MODERN), (MODERN, MODERN), ('legacy', '2025-11-25'),
])
async def test_official_clients_preserve_tools_resources_and_apps(rsa_keys, monkeypatch, mode, expected_version):
    import httpx2
    from mcp.client import Client, advertise
    from mcp.client.streamable_http import streamable_http_client

    private_key, _ = rsa_keys

    async def exchange(**kwargs):
        return {'access_token': _token(private_key, aud=[RESOURCE], azp='mcp-gateway'),
                'expires_in': 300}

    async def tools(**kwargs):
        return {'tools': [{'name': 'search_knowledge', 'inputSchema': {'type': 'object'},
                           '_meta': {'ui': {'resourceUri': UI_URI}}}]}

    async def call(**kwargs):
        return {'content': [{'type': 'text', 'text': 'found'}], 'structuredContent': {'hits': []}}

    async def read(**kwargs):
        return {'contents': [{'uri': UI_URI, 'mimeType': 'text/html;profile=mcp-app',
                              'text': '<main>Search</main>', '_meta': {'ui': {'csp': {}}}}]}

    monkeypatch.setattr('mcp_gateway.app.exchange_token', exchange)
    app = create_app(Settings(registry_path=str(REGISTRY)), jwt_signing_key=private_key,
                     tool_lister=tools, tool_caller=call, resource_reader=read)
    url = 'http://mcp-gateway:8082/mcp/knowledge'
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),
                          headers={'Authorization': f'Bearer {_token(private_key)}'}) as http,
        Client(streamable_http_client(url, http_client=http), mode=mode,
               extensions=[advertise('io.modelcontextprotocol/ui', {})]) as client,
    ):
        assert client.protocol_version == expected_version
        listed = await client.list_tools()
        assert listed.tools[0].meta['ui']['resourceUri'] == UI_URI
        result = await client.call_tool('search_knowledge', {'query': 'x'})
        assert result.structured_content == {'hits': []}
        resource = await client.read_resource(UI_URI)
        assert resource.contents[0].mime_type == 'text/html;profile=mcp-app'
        assert resource.contents[0].meta['ui']['csp'] == {}


async def test_parallel_users_and_servers_do_not_share_tokens_or_trace(rsa_keys, monkeypatch):
    import asyncio

    import httpx2
    from mcp.client import Client
    from mcp.client.streamable_http import streamable_http_client

    private_key, _ = rsa_keys
    seen = {}

    async def exchange(**kwargs):
        source = jwt.decode(kwargs['subject_token'], options={'verify_signature': False})
        resource = RESOURCE if kwargs['scope'] == 'mcp-tools' else WEB_SEARCH_RESOURCE
        await asyncio.sleep(0)
        return {'access_token': _token(private_key, sub=source['sub'], aud=[resource], azp='mcp-gateway'),
                'expires_in': 300}

    async def tools(**kwargs):
        return {'tools': [{'name': name, 'inputSchema': {'type': 'object'}}
                          for name in ('search_knowledge', 'search_web')]}

    async def call(**kwargs):
        claims = jwt.decode(kwargs['token'], options={'verify_signature': False})
        name = kwargs['arguments']['query']
        await asyncio.sleep(0)
        seen[name] = (claims['sub'], claims['aud'], kwargs['meta']['traceparent'], kwargs['url'])
        return {'content': [{'type': 'text', 'text': name}]}

    monkeypatch.setattr('mcp_gateway.app.exchange_token', exchange)
    app = create_app(Settings(registry_path=str(REGISTRY)), jwt_signing_key=private_key, tool_caller=call, tool_lister=tools)

    async def turn(user, server, tool, trace):
        token = _token(private_key, sub=user, realm_access={'roles': ['knowledge-mcp-reader', 'web-search-reader']})
        async with (
            httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),
                              headers={'Authorization': f'Bearer {token}'}) as http,
            Client(streamable_http_client(f'http://mcp-gateway:8082/mcp/{server}',
                                          http_client=http), mode=MODERN) as client,
        ):
            result = await client.call_tool(tool, {'query': user}, meta={'traceparent': trace})
            assert result.content[0].text == user

    trace_a = '00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-aaaaaaaaaaaaaaaa-01'
    trace_b = '00-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb-bbbbbbbbbbbbbbbb-01'
    async with app.router.lifespan_context(app):
        await asyncio.gather(turn('a', 'knowledge', 'search_knowledge', trace_a),
                             turn('b', 'web-search', 'search_web', trace_b))
    assert seen['a'] == ('a', [RESOURCE], trace_a, 'http://mcp-server:8000/mcp')
    assert seen['b'] == ('b', [WEB_SEARCH_RESOURCE], trace_b, 'http://web-search-mcp:8001/mcp')


@pytest.mark.parametrize('body', ['{', '[]', '{"jsonrpc":"2.0","id":1}', '[' * 12000 + ']' * 12000])
def test_malformed_messages_are_protocol_errors(rsa_keys, monkeypatch, body):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    response = client.post('/mcp/knowledge', content=body, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {_token(private_key)}',
    })
    assert response.status_code == 400
    assert 'error' in response.json()
    assert not seen


def test_body_limit_applies_to_legacy_envelope_guard(rsa_keys, monkeypatch):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    response = client.post('/mcp/knowledge', content=b'x' * (4 * 1024 * 1024 + 1), headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {_token(private_key)}',
    })
    assert response.status_code == 413
    assert not seen


def test_modern_forbidden_tool_is_denied_before_sdk_schema_lookup_exchange(rsa_keys, monkeypatch):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    body, headers = _modern_request('tools/call', {'name': 'hidden', 'arguments': {'query': 'x'}})
    response = client.post('/mcp/knowledge', json=body,
                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'})
    assert response.json()['error']['data']['status'] == 404
    assert 'subject_token' not in seen


@pytest.mark.parametrize('mode', ['legacy', MODERN])
def test_unknown_method_uses_sdk_protocol_error(rsa_keys, mode):
    private_key, _ = rsa_keys
    client = TestClient(create_app(Settings(registry_path=str(REGISTRY)), jwt_signing_key=private_key))
    body, headers = _modern_request('unknown/method') if mode == MODERN else (_rpc('unknown/method'), {})
    response = client.post('/mcp/knowledge', json=body,
                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'})
    assert response.json()['error']['code'] == -32601


async def test_cancelled_request_releases_handler_and_trace_context(rsa_keys, monkeypatch):
    import asyncio

    import httpx2
    from opentelemetry import trace

    private_key, _ = rsa_keys
    entered, released = asyncio.Event(), asyncio.Event()

    async def exchange(**kwargs):
        return {'access_token': _token(private_key, aud=[RESOURCE], azp='mcp-gateway'), 'expires_in': 300}

    async def call(**kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()

    monkeypatch.setattr('mcp_gateway.app.exchange_token', exchange)
    app = create_app(Settings(registry_path=str(REGISTRY)), jwt_signing_key=private_key, tool_caller=call)
    before = trace.get_current_span().get_span_context()
    body, headers = _modern_request('tools/call', {'name': 'search_knowledge', 'arguments': {}})
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as http,
    ):
        task = asyncio.create_task(http.post('http://mcp-gateway:8082/mcp/knowledge', json=body,
                                           headers={**headers, 'Authorization': f'Bearer {_token(private_key)}'}))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(released.wait(), 2)
    assert trace.get_current_span().get_span_context() == before


@pytest.mark.parametrize('rpc_id', [None, {}, True])
def test_guard_handles_invalid_request_ids_without_crashing(rsa_keys, monkeypatch, rpc_id):
    private_key, _ = rsa_keys
    seen = {}
    client = _apps_client(private_key, monkeypatch, seen=seen)
    body, _ = _modern_request('tools/list')
    body['id'] = rpc_id
    response = client.post('/mcp/knowledge', json=body,
                           headers={'Authorization': f'Bearer {_token(private_key)}'})
    assert response.status_code == 400
    assert 'error' in response.json()
    assert not seen
