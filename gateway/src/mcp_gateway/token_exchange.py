from __future__ import annotations

from typing import Any

import httpx

from mcp_gateway.errors import GatewayError

EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TYPE = "urn:ietf:params:oauth:token-type:access_token"


async def exchange_token(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    subject_token: str,
    scope: str,
    timeout_seconds: float,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    # Keycloak 26 V2: omit `audience`. Resource `aud` comes from mcp-tools mapper.
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds)
    try:
        response = await http.post(
            token_url,
            data={
                "grant_type": EXCHANGE_GRANT,
                "subject_token": subject_token,
                "subject_token_type": ACCESS_TYPE,
                "scope": scope,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
    except httpx.HTTPError as exc:
        raise GatewayError(503, "AUTH_SERVER_UNAVAILABLE", "Authorization server unavailable") from exc
    finally:
        if own_client:
            await http.aclose()

    if response.status_code >= 500:
        raise GatewayError(503, "AUTH_SERVER_UNAVAILABLE", "Authorization server unavailable")
    if response.status_code >= 400:
        raise GatewayError(502, "TOKEN_EXCHANGE_FAILED", "Token exchange failed")
    payload = response.json()
    if not payload.get("access_token"):
        raise GatewayError(502, "TOKEN_EXCHANGE_FAILED", "Token exchange failed")
    return payload
