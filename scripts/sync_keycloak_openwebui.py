"""Add/update only the Open WebUI client and owned scope in an existing realm."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote

import httpx

CLIENT_ID = "open-webui"
SCOPE_NAME = "open-webui-mcp-gateway"


def _request(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def _created_id(response: httpx.Response) -> str:
    location = response.headers.get("Location", "")
    if not location:
        raise RuntimeError("Keycloak did not return the new resource identifier")
    return location.rstrip("/").rsplit("/", 1)[-1]


def _upsert_mappers(client: httpx.Client, path: str, desired: list[dict]) -> None:
    current = _request(client, "GET", path).json()
    for mapper in desired:
        existing = next((item for item in current if item["name"] == mapper["name"]), None)
        payload = {key: value for key, value in mapper.items() if key != "id"}
        if existing is None:
            _request(client, "POST", path, json=payload)
        elif any(existing.get(key) != value for key, value in payload.items()):
            _request(client, "PUT", f"{path}/{existing['id']}", json={**existing, **payload})


def sync_openwebui(client: httpx.Client, realm: str, desired: dict, *, client_secret: str) -> None:
    base = f"/admin/realms/{quote(realm, safe='')}"
    scope = next(item for item in desired["clientScopes"] if item["name"] == SCOPE_NAME)
    app = next(item for item in desired["clients"] if item["clientId"] == CLIENT_ID)
    scopes = _request(client, "GET", base + "/client-scopes").json()
    scope_ids = {item["name"]: item["id"] for item in scopes}
    scope_id = scope_ids.get(SCOPE_NAME)
    if scope_id is None:
        payload = {key: value for key, value in scope.items() if key != "id"}
        scope_id = _created_id(_request(client, "POST", base + "/client-scopes", json=payload))
        scope_ids[SCOPE_NAME] = scope_id
    else:
        path = f"{base}/client-scopes/{scope_id}"
        existing = _request(client, "GET", path).json()
        payload = {
            key: value for key, value in scope.items() if key not in {"id", "protocolMappers"}
        }
        if any(existing.get(key) != value for key, value in payload.items()):
            _request(client, "PUT", path, json={**existing, **payload})
        _upsert_mappers(client, path + "/protocol-mappers/models", scope.get("protocolMappers", []))

    matches = _request(client, "GET", base + "/clients", params={"clientId": CLIENT_ID}).json()
    payload = {
        key: value
        for key, value in app.items()
        if key
        not in {"id", "defaultClientScopes", "optionalClientScopes", "protocolMappers", "secret"}
    }
    if not matches:
        client_id = _created_id(
            _request(client, "POST", base + "/clients", json={**payload, "secret": client_secret})
        )
    else:
        if len(matches) != 1 or matches[0]["clientId"] != CLIENT_ID:
            raise RuntimeError("Open WebUI client lookup is ambiguous")
        existing = matches[0]
        client_id = existing["id"]
        secret = (
            _request(client, "GET", f"{base}/clients/{client_id}/client-secret").json().get("value")
        )
        if secret != client_secret or any(
            existing.get(key) != value for key, value in payload.items()
        ):
            _request(
                client,
                "PUT",
                f"{base}/clients/{client_id}",
                json={**existing, **payload, "secret": client_secret},
            )

    path = f"{base}/clients/{client_id}/default-client-scopes"
    attached = {item["name"] for item in _request(client, "GET", path).json()}
    for name in app.get("defaultClientScopes", []):
        if name not in scope_ids:
            raise RuntimeError("Required default client scope is missing")
        if name not in attached:
            _request(client, "PUT", f"{path}/{scope_ids[name]}")
    if app.get("protocolMappers"):
        _upsert_mappers(
            client, f"{base}/clients/{client_id}/protocol-mappers/models", app["protocolMappers"]
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8081")
    parser.add_argument("--realm", default="knowledge")
    parser.add_argument(
        "--realm-file", type=Path, default=Path("infra/app/keycloak/knowledge-realm.json")
    )
    args = parser.parse_args()
    desired = json.loads(args.realm_file.read_text())
    app = next(item for item in desired["clients"] if item["clientId"] == CLIENT_ID)
    secret = os.getenv("OPEN_WEBUI_OAUTH_CLIENT_SECRET") or app.get("secret")
    if not secret:
        raise SystemExit("OPEN_WEBUI_OAUTH_CLIENT_SECRET is required")
    try:
        with httpx.Client(
            base_url=args.url.rstrip("/"), timeout=30, follow_redirects=False
        ) as client:
            response = _request(
                client,
                "POST",
                "/realms/master/protocol/openid-connect/token",
                data={
                    "grant_type": "password",
                    "client_id": "admin-cli",
                    "username": os.getenv("KC_BOOTSTRAP_ADMIN_USERNAME", "admin"),
                    "password": os.getenv("KC_BOOTSTRAP_ADMIN_PASSWORD", "admin"),
                },
            )
            client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
            sync_openwebui(client, args.realm, desired, client_secret=secret)
    except httpx.HTTPStatusError as error:
        raise SystemExit(f"Keycloak sync failed (HTTP {error.response.status_code})") from None
    except httpx.RequestError:
        raise SystemExit("Keycloak sync failed: server is unavailable") from None
    print("Open WebUI OAuth client and scope are synchronized")


if __name__ == "__main__":
    main()
