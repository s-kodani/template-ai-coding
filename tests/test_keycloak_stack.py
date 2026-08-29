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
    ):
        assert f"{name}=" in text
    assert "OAUTH_GENERIC_NAME=keycloak" in text
    assert "OAUTH_KEYCLOAK_NAME=unused" in text
    assert "OAUTH_GENERIC_CLIENT_SECRET=chainlit-local-secret" in text
    assert "localhost:8081" in text


def test_default_up_includes_app_stack_that_now_has_keycloak() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    compose = _compose()

    assert "up: langfuse-up app-up" in makefile
    assert "keycloak" in compose["services"]
    assert "langflow" not in compose["services"]
