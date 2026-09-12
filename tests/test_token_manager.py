from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

import pytest

from chat_ui.token_manager import (
    REAUTH_REQUIRED_DETAIL,
    KeycloakTokenManager,
    MemoryTokenStore,
    PostgresTokenStore,
    ReauthRequired,
    StoredTokens,
)


def _unsigned(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"h.{body}.s"


@pytest.mark.asyncio
async def test_memory_store_roundtrip_by_session() -> None:
    store = MemoryTokenStore()
    mgr = KeycloakTokenManager(store)
    token = _unsigned({"sub": "sub-1", "exp": 1_900_000_000})
    saved = await mgr.save_response({"access_token": token, "refresh_token": "rt-abc"})
    assert saved is not None
    await mgr.bind_session("sub-1", "sess-1")
    assert await mgr.get_access_token("sess-1") == token


@pytest.mark.asyncio
async def test_get_access_token_skips_refresh_when_not_expired() -> None:
    store = MemoryTokenStore()
    mgr = KeycloakTokenManager(store, token_url="http://idp/token")
    token = _unsigned({"sub": "s1", "exp": 1_900_000_000})
    await mgr.save_response({"access_token": token, "refresh_token": "rt"})
    await mgr.bind_session("s1", "sess")
    assert await mgr.get_access_token("sess") == token


@pytest.mark.asyncio
async def test_save_response_returns_none_without_sub() -> None:
    mgr = KeycloakTokenManager(MemoryTokenStore())
    token = _unsigned({"exp": 1_900_000_000})
    assert await mgr.save_response({"access_token": token, "refresh_token": "rt"}) is None


@pytest.mark.asyncio
async def test_get_access_token_force_refresh_uses_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MemoryTokenStore()
    mgr = KeycloakTokenManager(
        store,
        token_url="http://idp/token",
        client_id="chainlit",
        client_secret="secret",
    )
    token = _unsigned({"sub": "s1", "exp": 1_900_000_000})
    await mgr.save_response({"access_token": token, "refresh_token": "rt"})
    await mgr.bind_session("s1", "sess")

    refreshed = _unsigned({"sub": "s1", "exp": 1_900_000_100})

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {"access_token": refreshed, "refresh_token": "rt2"}

    fake_client = AsyncMock()
    fake_client.__aenter__.return_value.post = AsyncMock(return_value=FakeResponse())
    fake_client.__aexit__.return_value = None
    monkeypatch.setattr("chat_ui.token_manager.httpx.AsyncClient", lambda **_: fake_client)

    got = await mgr.get_access_token("sess", force_refresh=True)
    assert got == refreshed


@pytest.mark.asyncio
async def test_postgres_store_upserts_when_refresh_token_is_missing() -> None:
    import asyncpg

    url = "postgresql://knowledge:change-me@localhost:5433/knowledge"
    try:
        conn = await asyncpg.connect(url, timeout=2)
    except (OSError, asyncpg.PostgresError):
        pytest.skip("app postgres is not available")
    await conn.close()

    store = PostgresTokenStore(url, "test-token-store-key")
    token = _unsigned({"sub": "sub-null-rt", "exp": 1_900_000_000})
    await store.upsert(
        StoredTokens(access_token=token, refresh_token=None, expires_at=1_900_000_000, subject="sub-null-rt"),
        session_id="sess-null-rt",
    )
    loaded = await store.get_by_session("sess-null-rt")
    assert loaded is not None
    assert loaded.access_token == token
    assert loaded.refresh_token is None
    await store.delete_by_session("sess-null-rt")


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def _patch_post(monkeypatch: pytest.MonkeyPatch, post: AsyncMock) -> None:
    fake_client = AsyncMock()
    fake_client.__aenter__.return_value.post = post
    fake_client.__aexit__.return_value = None
    monkeypatch.setattr("chat_ui.token_manager.httpx.AsyncClient", lambda **_: fake_client)


async def _expired_manager(store: MemoryTokenStore) -> KeycloakTokenManager:
    mgr = KeycloakTokenManager(
        store,
        token_url="http://idp/token",
        client_id="chainlit",
        client_secret="secret",
    )
    await mgr.save_response(
        {
            "access_token": _unsigned({"sub": "s1", "exp": 1_000_000_000}),
            "refresh_token": "rt-secret-value",
        }
    )
    await mgr.bind_session("s1", "sess")
    return mgr


@pytest.mark.asyncio
async def test_rejected_refresh_requires_reauth_and_drops_stored_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryTokenStore()
    mgr = await _expired_manager(store)
    _patch_post(monkeypatch, AsyncMock(return_value=_Response(400, {"error": "invalid_grant"})))

    with pytest.raises(ReauthRequired):
        await mgr.get_access_token("sess")

    assert await store.get_by_session("sess") is None


@pytest.mark.asyncio
async def test_upstream_refresh_failure_keeps_stored_tokens(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = MemoryTokenStore()
    mgr = await _expired_manager(store)
    _patch_post(monkeypatch, AsyncMock(return_value=_Response(503)))

    with caplog.at_level("WARNING"):
        assert await mgr.get_access_token("sess") is None
    assert await store.get_by_session("sess") is not None
    assert "503" in caplog.text
    assert "rt-secret-value" not in caplog.text


@pytest.mark.asyncio
async def test_misconfigured_client_does_not_force_reauth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """invalid_client means a broken client secret, not a dead SSO session."""
    store = MemoryTokenStore()
    mgr = await _expired_manager(store)
    _patch_post(monkeypatch, AsyncMock(return_value=_Response(401, {"error": "invalid_client"})))

    assert await mgr.get_access_token("sess") is None
    assert await store.get_by_session("sess") is not None


@pytest.mark.asyncio
async def test_transport_refresh_failure_keeps_stored_tokens(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import httpx

    store = MemoryTokenStore()
    mgr = await _expired_manager(store)
    _patch_post(monkeypatch, AsyncMock(side_effect=httpx.ConnectError("boom")))

    with caplog.at_level("WARNING"):
        assert await mgr.get_access_token("sess") is None
    assert await store.get_by_session("sess") is not None
    assert "ConnectError" in caplog.text
    assert "rt-secret-value" not in caplog.text


def test_reauth_detail_tells_the_user_what_to_do() -> None:
    assert "再ログイン" in REAUTH_REQUIRED_DETAIL


@pytest.mark.asyncio
async def test_rejected_refresh_does_not_log_token_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = MemoryTokenStore()
    mgr = await _expired_manager(store)
    _patch_post(monkeypatch, AsyncMock(return_value=_Response(400, {"error": "invalid_grant"})))

    with caplog.at_level("WARNING"), pytest.raises(ReauthRequired):
        await mgr.get_access_token("sess")

    logged = caplog.text
    assert "invalid_grant" in logged
    assert "rt-secret-value" not in logged
