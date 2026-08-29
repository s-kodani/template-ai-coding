from __future__ import annotations

from typing import Any

import pytest
from chainlit.user import User

from chat_ui.auth import (
    KEYCLOAK_ENV,
    KEYCLOAK_PROVIDER_ID,
    accept_oauth_user,
    keycloak_oauth_configured,
    register_oauth_callback,
)


def _user(identifier: str = "dev@localhost") -> User:
    return User(identifier=identifier, metadata={"provider": "keycloak"})


def test_accepts_keycloak_user_with_identifier() -> None:
    user = _user()

    accepted = accept_oauth_user(KEYCLOAK_PROVIDER_ID, user)

    assert accepted is user
    assert accepted.identifier == "dev@localhost"


def test_rejects_non_keycloak_provider() -> None:
    assert accept_oauth_user("github", _user()) is None


def test_rejects_keycloak_user_without_identifier() -> None:
    assert accept_oauth_user(KEYCLOAK_PROVIDER_ID, _user("")) is None


@pytest.mark.parametrize("missing", KEYCLOAK_ENV)
def test_keycloak_oauth_configured_requires_all_env(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    for name in KEYCLOAK_ENV:
        monkeypatch.setenv(name, "set")
    monkeypatch.delenv(missing, raising=False)

    assert keycloak_oauth_configured() is False


def test_keycloak_oauth_configured_when_all_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KEYCLOAK_ENV:
        monkeypatch.setenv(name, "set")

    assert keycloak_oauth_configured() is True


@pytest.mark.asyncio
async def test_register_oauth_callback_accepts_keycloak_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in KEYCLOAK_ENV:
        monkeypatch.setenv(name, "set")

    from chainlit.config import config

    config.code.oauth_callback = None
    assert register_oauth_callback() is True
    assert config.code.oauth_callback is not None

    default_user = _user()
    accepted: Any = await config.code.oauth_callback(
        KEYCLOAK_PROVIDER_ID,
        "token",
        {"email": "dev@localhost"},
        default_user,
    )
    assert accepted is default_user


def test_register_oauth_callback_skips_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KEYCLOAK_ENV:
        monkeypatch.delenv(name, raising=False)

    from chainlit.config import config

    config.code.oauth_callback = None
    assert register_oauth_callback() is False
    assert config.code.oauth_callback is None
