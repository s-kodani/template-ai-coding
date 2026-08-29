from __future__ import annotations

import os

import chainlit as cl
from chainlit.user import User

KEYCLOAK_PROVIDER_ID = "keycloak"
KEYCLOAK_ENV = (
    "OAUTH_KEYCLOAK_CLIENT_ID",
    "OAUTH_KEYCLOAK_CLIENT_SECRET",
    "OAUTH_KEYCLOAK_REALM",
    "OAUTH_KEYCLOAK_BASE_URL",
)


def keycloak_oauth_configured() -> bool:
    return all(os.environ.get(name) for name in KEYCLOAK_ENV)


def accept_oauth_user(provider_id: str, default_app_user: User) -> User | None:
    if provider_id != KEYCLOAK_PROVIDER_ID:
        return None
    if not default_app_user.identifier:
        return None
    return default_app_user


def register_oauth_callback() -> bool:
    if not keycloak_oauth_configured():
        return False

    @cl.oauth_callback
    async def oauth_callback(
        provider_id: str,
        token: str,
        raw_user_data: dict[str, str],
        default_app_user: User,
        id_token: str | None = None,
    ) -> User | None:
        del token, raw_user_data, id_token
        return accept_oauth_user(provider_id, default_app_user)

    return True
