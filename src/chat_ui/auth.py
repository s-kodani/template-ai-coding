from __future__ import annotations

import os
from contextvars import ContextVar

import chainlit as cl
from chainlit.oauth_providers import GenericOAuthProvider
from chainlit.user import User

from chat_ui.jwt_util import jwt_claims
from chat_ui.token_manager import KeycloakTokenManager

KEYCLOAK_PROVIDER_ID = "keycloak"
OAUTH_ENV = (
    "OAUTH_GENERIC_CLIENT_ID",
    "OAUTH_GENERIC_CLIENT_SECRET",
    "OAUTH_GENERIC_AUTH_URL",
    "OAUTH_GENERIC_TOKEN_URL",
    "OAUTH_GENERIC_USER_INFO_URL",
    "OAUTH_GENERIC_SCOPES",
)

_raw_token_response: ContextVar[dict | None] = ContextVar("kc_raw_token", default=None)
_token_manager: KeycloakTokenManager | None = None
_oauth_capture_installed = False
_original_get_raw_token_response = GenericOAuthProvider.get_raw_token_response


def keycloak_oauth_configured() -> bool:
    return all(os.environ.get(name) for name in OAUTH_ENV)


def set_token_manager(manager: KeycloakTokenManager | None) -> None:
    global _token_manager
    _token_manager = manager


def stash_token_response(payload: dict | None) -> None:
    _raw_token_response.set(payload)


def install_oauth_token_capture() -> None:
    """Keep refresh_token from the token endpoint; GenericOAuthProvider.get_token drops it."""
    global _oauth_capture_installed
    if _oauth_capture_installed:
        return

    async def wrapped(self: GenericOAuthProvider, code: str, url: str) -> dict:
        data = await _original_get_raw_token_response(self, code, url)
        _raw_token_response.set(data)
        return data

    GenericOAuthProvider.get_raw_token_response = wrapped  # type: ignore[method-assign]
    _oauth_capture_installed = True


def accept_oauth_user(provider_id: str, default_app_user: User) -> User | None:
    if provider_id != KEYCLOAK_PROVIDER_ID:
        return None
    if not default_app_user.identifier:
        return None
    return default_app_user


def register_oauth_callback() -> bool:
    if not keycloak_oauth_configured():
        return False

    install_oauth_token_capture()

    @cl.oauth_callback
    async def oauth_callback(
        provider_id: str,
        token: str,
        raw_user_data: dict[str, str],
        default_app_user: User,
        id_token: str | None = None,
    ) -> User | None:
        del raw_user_data, id_token
        user = accept_oauth_user(provider_id, default_app_user)
        if user is None:
            return None
        captured = _raw_token_response.get()
        _raw_token_response.set(None)
        metadata = dict(user.metadata or {})
        subject = ""
        if _token_manager is not None:
            saved = await _token_manager.save_response(captured or {}, access_token=token)
            if saved is not None:
                subject = saved.subject
        if not subject:
            subject = str(jwt_claims(token).get("sub") or "")
        if subject:
            metadata["keycloak_sub"] = subject
        return User(identifier=user.identifier, metadata=metadata)

    return True
