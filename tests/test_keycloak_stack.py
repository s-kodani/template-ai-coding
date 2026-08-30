from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "infra" / "app" / "compose.yml"
REALM_PATH = ROOT / "infra" / "app" / "keycloak" / "knowledge-realm.json"
ENV_EXAMPLE = ROOT / ".env.example"
MAKEFILE = ROOT / "infra" / "Makefile"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def _realm() -> dict:
    return json.loads(REALM_PATH.read_text(encoding="utf-8"))


def test_app_compose_runs_keycloak_with_realm_import() -> None:
    compose = _compose()
    keycloak = compose["services"]["keycloak"]

    assert keycloak["image"].startswith("keycloak/keycloak:26.")
    assert "--import-realm" in keycloak["command"]
    assert "8081:8080" in keycloak["ports"]
    volumes = keycloak["volumes"]
    assert any(str(item).endswith(":/opt/keycloak/data/import/knowledge-realm.json:ro") for item in volumes)
    env = keycloak["environment"]
    assert env["KC_HTTP_ENABLED"] == "true"
    assert env["KC_HOSTNAME"] == "http://localhost:8081"
    assert env["KC_HEALTH_ENABLED"] == "true"


def test_chainlit_waits_for_keycloak_and_splits_browser_and_backchannel_urls() -> None:
    compose = _compose()
    chainlit = compose["services"]["chainlit"]

    assert "extra_hosts" not in chainlit
    assert chainlit["depends_on"]["keycloak"]["condition"] == "service_healthy"
    env = chainlit["environment"]
    assert env["CHAINLIT_URL"] == "http://localhost:8080"
    assert env["DATABASE_URL"] == ""
    assert "CHAINLIT_AUTH_SECRET" in env
    assert env["OAUTH_GENERIC_NAME"] == "keycloak"
    assert env["OAUTH_KEYCLOAK_NAME"] == "unused"
    assert env["OAUTH_GENERIC_CLIENT_ID"] == "${OAUTH_GENERIC_CLIENT_ID:-chainlit}"
    assert "localhost:8081" in env["OAUTH_GENERIC_AUTH_URL"]
    assert "keycloak:8080" in env["OAUTH_GENERIC_TOKEN_URL"]
    assert "keycloak:8080" in env["OAUTH_GENERIC_USER_INFO_URL"]


def test_realm_defines_chainlit_client_and_dev_user() -> None:
    realm = _realm()

    assert realm["realm"] == "knowledge"
    assert realm["enabled"] is True
    assert realm["sslRequired"] == "none"

    clients = {client["clientId"]: client for client in realm["clients"]}
    chainlit = clients["chainlit"]
    assert chainlit["enabled"] is True
    assert chainlit["publicClient"] is False
    assert chainlit["secret"] == "chainlit-local-secret"
    assert chainlit["standardFlowEnabled"] is True
    assert "http://localhost:8080/auth/oauth/keycloak/callback" in chainlit["redirectUris"]
    assert "http://127.0.0.1:8080/auth/oauth/keycloak/callback" in chainlit["redirectUris"]

    users = {user["username"]: user for user in realm["users"]}
    dev = users["dev"]
    assert dev["enabled"] is True
    assert dev["email"] == "dev@localhost"
    assert dev["emailVerified"] is True
    passwords = [item["value"] for item in dev["credentials"] if item["type"] == "password"]
    assert passwords == ["dev"]
    assert "knowledge-mcp-reader" in (dev.get("realmRoles") or [])
    assert "mcp-reader" not in (dev.get("realmRoles") or [])


def _client_scope(realm: dict, name: str) -> dict:
    scopes = {scope["name"]: scope for scope in realm.get("clientScopes") or []}
    return scopes[name]


def _audience_mapper_config(scope: dict, mapper_name: str) -> dict:
    mappers = {mapper["name"]: mapper for mapper in scope.get("protocolMappers") or []}
    return mappers[mapper_name]["config"]


def test_realm_defines_mcp_gateway_and_knowledge_mcp_clients() -> None:
    realm = _realm()
    clients = {client["clientId"]: client for client in realm["clients"]}

    gateway = clients["mcp-gateway"]
    assert gateway["publicClient"] is False
    assert gateway["standardFlowEnabled"] is False
    assert gateway["directAccessGrantsEnabled"] is False
    assert gateway["implicitFlowEnabled"] is False
    assert gateway["attributes"]["standard.token.exchange.enabled"] == "true"
    assert gateway["secret"] == "mcp-gateway-local-secret"

    mcp = clients["knowledge-mcp"]
    assert mcp["enabled"] is True
    assert mcp["standardFlowEnabled"] is False
    assert mcp["directAccessGrantsEnabled"] is False
    assert mcp["implicitFlowEnabled"] is False


def test_realm_keeps_oidc_scopes_needed_for_sub_email_and_roles() -> None:
    realm = _realm()
    names = {scope["name"] for scope in realm.get("clientScopes") or []}
    for required in ("basic", "profile", "email", "roles"):
        assert required in names

    chainlit = next(client for client in realm["clients"] if client["clientId"] == "chainlit")
    for required in ("basic", "profile", "email", "roles", "chainlit-mcp-gateway"):
        assert required in (chainlit.get("defaultClientScopes") or [])

    gateway = next(client for client in realm["clients"] if client["clientId"] == "mcp-gateway")
    for required in ("basic", "roles", "mcp-tools"):
        assert required in (gateway.get("defaultClientScopes") or [])

    sub_mappers = [
        mapper
        for mapper in _client_scope(realm, "basic").get("protocolMappers") or []
        if mapper.get("protocolMapper") == "oidc-sub-mapper"
    ]
    assert sub_mappers
    assert sub_mappers[0]["config"]["access.token.claim"] == "true"

    roles_mappers = {
        mapper["name"]: mapper for mapper in _client_scope(realm, "roles").get("protocolMappers") or []
    }
    assert roles_mappers["realm roles"]["config"]["claim.name"] == "realm_access.roles"
    assert roles_mappers["realm roles"]["config"]["access.token.claim"] == "true"


def test_realm_audience_mappers_bind_gateway_and_mcp_resource() -> None:
    realm = _realm()
    chainlit = next(client for client in realm["clients"] if client["clientId"] == "chainlit")
    assert "chainlit-mcp-gateway" in (chainlit.get("defaultClientScopes") or [])

    gateway_aud = _audience_mapper_config(
        _client_scope(realm, "chainlit-mcp-gateway"), "mcp-gateway-audience"
    )
    assert gateway_aud["included.client.audience"] == "mcp-gateway"
    assert gateway_aud["access.token.claim"] == "true"

    resource_aud = _audience_mapper_config(_client_scope(realm, "mcp-tools"), "knowledge-mcp-resource")
    assert resource_aud["included.custom.audience"] == "http://localhost:8000/mcp"


def test_realm_defines_mcp_reader_role_and_readerless_user() -> None:
    realm = _realm()
    role_names = [role["name"] for role in (realm.get("roles") or {}).get("realm") or []]
    assert "knowledge-mcp-reader" in role_names
    assert "mcp-reader" not in role_names

    users = {user["username"]: user for user in realm["users"]}
    assert "knowledge-mcp-reader" not in (users["readerless"].get("realmRoles") or [])
    assert "mcp-reader" not in (users["readerless"].get("realmRoles") or [])
    assert users["readerless"]["enabled"] is True


def test_env_example_documents_keycloak_oauth() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    for name in (
        "CHAINLIT_AUTH_SECRET",
        "CHAINLIT_URL",
        "OAUTH_GENERIC_CLIENT_ID",
        "OAUTH_GENERIC_CLIENT_SECRET",
        "OAUTH_GENERIC_AUTH_URL",
        "OAUTH_GENERIC_TOKEN_URL",
        "OAUTH_GENERIC_USER_INFO_URL",
        "OAUTH_GENERIC_SCOPES",
        "OAUTH_GENERIC_NAME",
        "OAUTH_KEYCLOAK_NAME",
        "KC_BOOTSTRAP_ADMIN_USERNAME",
        "KC_BOOTSTRAP_ADMIN_PASSWORD",
        "MCP_GATEWAY_URL",
        "TOKEN_STORE_DATABASE_URL",
        "TOKEN_STORE_KEY",
        "MCP_JWKS_URI",
        "MCP_AUDIENCE",
        "GATEWAY_CLIENT_SECRET",
    ):
        assert f"{name}=" in text
    assert "OAUTH_GENERIC_NAME=keycloak" in text
    assert "OAUTH_KEYCLOAK_NAME=unused" in text
    assert "OAUTH_GENERIC_CLIENT_SECRET=chainlit-local-secret" in text
    assert "localhost:8081" in text
    assert "MCP_GATEWAY_URL=" in text
    assert "TOKEN_STORE_DATABASE_URL=" in text
    assert "MCP_AUDIENCE=http://localhost:8000/mcp" in text


def test_default_up_includes_app_stack_that_now_has_keycloak() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    compose = _compose()

    assert "up: langfuse-up app-up" in makefile
    assert "keycloak" in compose["services"]
    assert "langflow" not in compose["services"]


def test_compose_defines_internal_mcp_gateway() -> None:
    compose = _compose()
    gateway = compose["services"]["mcp-gateway"]
    chainlit = compose["services"]["chainlit"]
    mcp_server = compose["services"]["mcp-server"]

    assert "ports" not in gateway
    assert gateway["build"]["dockerfile"] == "infra/app/Dockerfile.gateway"
    assert chainlit["environment"]["MCP_GATEWAY_URL"] == "http://mcp-gateway:8082"
    assert chainlit["environment"]["DATABASE_URL"] == ""
    assert "TOKEN_STORE_DATABASE_URL" in chainlit["environment"]
    assert mcp_server["environment"]["MCP_JWKS_URI"].startswith("http://keycloak:8080/")
    assert mcp_server["environment"]["MCP_AUDIENCE"] == "http://localhost:8000/mcp"
    assert chainlit["depends_on"]["mcp-gateway"]["condition"] == "service_healthy"


def test_mcp_dev_token_script_omits_keycloak_v2_audience() -> None:
    text = (ROOT / "scripts" / "mcp_dev_token.py").read_text(encoding="utf-8")
    assert '"audience"' not in text
    assert '"scope": "mcp-tools"' in text
