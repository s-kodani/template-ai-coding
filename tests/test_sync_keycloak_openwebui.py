from __future__ import annotations

import json

import httpx


def test_sync_is_idempotent_and_keeps_existing_clients_and_mappers():
    from scripts.sync_keycloak_openwebui import sync_openwebui

    scopes = [{"id": "roles-id", "name": "roles"}, {"id": "basic-id", "name": "basic"}]
    clients = [{"id": "chainlit-id", "clientId": "chainlit", "secret": "do-not-change"}]
    mappers = {}
    defaults = {}
    mutations = []

    def handler(request):
        path = request.url.path
        payload = json.loads(request.content) if request.content else None
        if request.method == "GET" and path.endswith("/client-scopes"):
            return httpx.Response(200, json=scopes)
        if request.method == "POST" and path.endswith("/client-scopes"):
            scopes.append({**payload, "id": "new-scope"})
            mutations.append((request.method, path))
            mappers["new-scope"] = payload.get("protocolMappers", [])
            return httpx.Response(201, headers={"Location": path + "/new-scope"})
        if request.method == "GET" and path.endswith("/clients"):
            return httpx.Response(
                200,
                json=[
                    item
                    for item in clients
                    if item["clientId"] == request.url.params.get("clientId")
                ],
            )
        if request.method == "POST" and path.endswith("/clients"):
            clients.append({**payload, "id": "new-client"})
            defaults["new-client"] = []
            mutations.append((request.method, path))
            return httpx.Response(201, headers={"Location": path + "/new-client"})
        if request.method == "GET" and path.endswith("/default-client-scopes"):
            return httpx.Response(200, json=defaults["new-client"])
        if request.method == "PUT" and "/default-client-scopes/" in path:
            scope_id = path.rsplit("/", 1)[1]
            defaults["new-client"].append(next(item for item in scopes if item["id"] == scope_id))
            mutations.append((request.method, path))
            return httpx.Response(204)
        if request.method == "GET" and path.endswith("/protocol-mappers/models"):
            return httpx.Response(200, json=mappers.get("new-scope", []))
        if request.method == "GET" and "/client-scopes/" in path:
            return httpx.Response(
                200, json=next(item for item in scopes if item["id"] == path.rsplit("/", 1)[1])
            )
        if request.method == "GET" and path.endswith("/client-secret"):
            return httpx.Response(200, json={"type": "secret", "value": clients[-1]["secret"]})
        if request.method == "GET" and "/clients/" in path:
            return httpx.Response(200, json=clients[-1])
        raise AssertionError(f"Unexpected mutation or request: {request.method} {path}")

    desired = {
        "clientScopes": [
            {
                "name": "open-webui-mcp-gateway",
                "protocol": "openid-connect",
                "protocolMappers": [
                    {"name": "mcp-roles", "protocolMapper": "oidc-usermodel-realm-role-mapper"}
                ],
            }
        ],
        "clients": [
            {
                "clientId": "open-webui",
                "secret": "example",
                "protocol": "openid-connect",
                "defaultClientScopes": ["basic", "roles", "open-webui-mcp-gateway"],
            }
        ],
    }
    with httpx.Client(base_url="http://keycloak", transport=httpx.MockTransport(handler)) as client:
        sync_openwebui(client, "knowledge", desired, client_secret="new-secret")
        first_mutations = len(mutations)
        sync_openwebui(client, "knowledge", desired, client_secret="new-secret")
    assert len(mutations) == first_mutations
    assert clients[0] == {"id": "chainlit-id", "clientId": "chainlit", "secret": "do-not-change"}
    assert clients[-1]["secret"] == "new-secret"
    assert {item["name"] for item in defaults["new-client"]} == {
        "basic",
        "roles",
        "open-webui-mcp-gateway",
    }
