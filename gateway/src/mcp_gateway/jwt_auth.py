from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient

from mcp_gateway.errors import GatewayError
from mcp_gateway.principal import Principal

_jwks_clients: dict[str, PyJWKClient] = {}


def _verification_key(signing_key: Any) -> Any:
    public_key = getattr(signing_key, "public_key", None)
    if callable(public_key):
        return public_key()
    return signing_key


def _jwks_client(jwks_uri: str) -> PyJWKClient:
    cached = _jwks_clients.get(jwks_uri)
    if cached is None:
        cached = PyJWKClient(jwks_uri, cache_keys=True)
        _jwks_clients[jwks_uri] = cached
    return cached


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def verify_chainlit_token(
    token: str,
    *,
    issuer: str,
    jwks_uri: str,
    audience: str,
    azp: str,
    signing_key: Any | None = None,
) -> Principal:
    try:
        if signing_key is None:
            signing_key = _jwks_client(jwks_uri).get_signing_key_from_jwt(token).key
        else:
            signing_key = _verification_key(signing_key)
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["iss", "sub", "exp", "aud"], "verify_aud": False},
            leeway=5,
        )
    except jwt.ExpiredSignatureError as exc:
        raise GatewayError(401, "TOKEN_EXPIRED", "Access token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise GatewayError(401, "INVALID_TOKEN", "Access token is invalid") from exc

    audiences = _as_list(claims.get("aud"))
    if audience not in audiences:
        raise GatewayError(403, "INVALID_AUDIENCE", "Token is not for mcp-gateway")
    if claims.get("azp") != azp:
        raise GatewayError(403, "INVALID_AUDIENCE", "Token authorized party is not chainlit")
    subject = claims.get("sub")
    if not subject:
        raise GatewayError(401, "INVALID_TOKEN", "Access token is missing subject")

    realm_roles = set((claims.get("realm_access") or {}).get("roles") or [])
    scopes = set(str(claims.get("scope") or "").split())
    return Principal(
        subject=str(subject),
        issuer=str(claims.get("iss") or issuer),
        authorized_party=str(claims.get("azp") or azp),
        roles=frozenset(str(role) for role in realm_roles),
        scopes=frozenset(scopes),
        token=token,
    )


def verify_exchanged_token(
    token: str,
    *,
    issuer: str,
    expected_audience: str,
    signing_key: Any | None = None,
    jwks_uri: str = "",
) -> dict[str, Any]:
    try:
        if signing_key is None:
            signing_key = _jwks_client(jwks_uri).get_signing_key_from_jwt(token).key
        else:
            signing_key = _verification_key(signing_key)
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["iss", "sub", "exp", "aud"], "verify_aud": False},
            leeway=5,
        )
    except jwt.InvalidTokenError as exc:
        raise GatewayError(502, "TOKEN_EXCHANGE_FAILED", "Exchanged token is invalid") from exc
    if expected_audience not in _as_list(claims.get("aud")):
        raise GatewayError(502, "TOKEN_AUDIENCE_MISMATCH", "Exchanged token audience mismatch")
    return claims
