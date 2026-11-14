"""Deployment contracts that protect SSO and the MCP token boundary."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def stack() -> dict:
    return yaml.safe_load((ROOT / "infra/app/compose.yml").read_text())


def realm() -> dict:
    return json.loads((ROOT / "infra/app/keycloak/knowledge-realm.json").read_text())


def test_openwebui_uses_sso_and_keeps_oauth_tokens_out_of_browser_configuration() -> None:
    services = stack()["services"]
    assert "chainlit" not in services
    ui = services["open-webui"]
    env = ui["environment"]
    assert ui["ports"] == ["8080:8080"]
    assert env["ENABLE_LOGIN_FORM"] == "false"
    assert env["ENABLE_SIGNUP"] == "false"
    assert env["ENABLE_OAUTH_SIGNUP"] == "true"
    assert env["OAUTH_CLIENT_ID"] == "open-webui"
    assert env["OPENID_REDIRECT_URI"] == "http://localhost:8080/oauth/oidc/callback"
    assert env["OPENID_PROVIDER_URL"].startswith("http://keycloak:8080/")
    assert env["OAUTH_CODE_CHALLENGE_METHOD"] == "S256"
    assert "WEBUI_SECRET_KEY" in env
    assert env["DATABASE_URL"] == "sqlite:////app/backend/data/webui.db"
    assert any("/app/backend/data" in volume for volume in ui["volumes"])
    assert "TOKEN_STORE_KEY" not in env
    assert env["ENABLE_OTEL"] == "false"


def test_new_ui_role_sync_cannot_create_groups_or_bypass_mcp_grants() -> None:
    env = stack()["services"]["open-webui"]["environment"]
    assert env["OAUTH_GROUPS_CLAIM"] == "mcp_roles"
    assert env["ENABLE_OAUTH_GROUP_MANAGEMENT"] == "true"
    assert env["ENABLE_OAUTH_GROUP_CREATION"] == "false"
    assert env["BYPASS_ADMIN_ACCESS_CONTROL"] == "false"
    assert env["ENABLE_PERSISTENT_CONFIG"] == "false"
    assert env["ENABLE_OAUTH_PERSISTENT_CONFIG"] == "false"
    assert env["JWT_EXPIRES_IN"] == "10h"
    assert realm()["ssoSessionMaxLifespan"] >= 10 * 3600


def test_gateway_only_accepts_the_new_ui_and_stays_internal() -> None:
    gateway = stack()["services"]["mcp-gateway"]
    assert "ports" not in gateway
    assert gateway["environment"]["GATEWAY_AZP"] == "open-webui"
    assert gateway["environment"]["GATEWAY_AUDIENCE"] == "mcp-gateway"


def test_openwebui_realm_client_has_gateway_audience_and_id_token_roles() -> None:
    data = realm()
    client = next(item for item in data["clients"] if item["clientId"] == "open-webui")
    assert client["publicClient"] is False
    assert client["standardFlowEnabled"] is True
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert "http://localhost:8080/oauth/oidc/callback" in client["redirectUris"]
    assert "open-webui-mcp-gateway" in client["defaultClientScopes"]
    scope = next(item for item in data["clientScopes"] if item["name"] == "open-webui-mcp-gateway")
    mappers = scope["protocolMappers"]
    audience = next(item for item in mappers if item["protocolMapper"] == "oidc-audience-mapper")
    assert audience["config"]["included.client.audience"] == "mcp-gateway"
    assert audience["config"]["access.token.claim"] == "true"
    roles = next(item for item in mappers if item["protocolMapper"] == "oidc-usermodel-realm-role-mapper")
    assert roles["config"]["claim.name"] == "mcp_roles"
    for claim in ("id.token.claim", "userinfo.token.claim", "access.token.claim", "multivalued"):
        assert roles["config"][claim] == "true"


def test_existing_realm_is_synced_before_openwebui_serves_requests() -> None:
    services = stack()["services"]
    sync = services["keycloak-sync"]
    assert sync["depends_on"]["keycloak"]["condition"] == "service_healthy"
    assert services["open-webui"]["depends_on"]["keycloak-sync"]["condition"] == "service_completed_successfully"
    command = " ".join(sync["command"])
    assert "sync_keycloak_openwebui.py" in command
    assert "--import-realm" not in command


def test_keycloak_identity_survives_recreation_of_the_ui_and_idp() -> None:
    data = stack()
    assert "keycloak_data:/opt/keycloak/data" in data["services"]["keycloak"]["volumes"]
    assert "keycloak_data" in data["volumes"]
    makefile = (ROOT / "infra/Makefile").read_text()
    assert "app-up: network preserve-keycloak" in makefile
    assert "scripts/persist_keycloak_data.py" in makefile
