from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

import asyncpg
import httpx

from chat_ui.jwt_util import jwt_claims
from knowledge_mcp.config import Settings


@dataclass
class StoredTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float
    subject: str


class TokenStore(Protocol):
    async def upsert(self, tokens: StoredTokens, session_id: str | None = None) -> None: ...
    async def get_by_session(self, session_id: str) -> StoredTokens | None: ...
    async def bind_session(self, subject: str, session_id: str) -> None: ...
    async def delete_by_session(self, session_id: str) -> None: ...


class MemoryTokenStore:
    def __init__(self) -> None:
        self.by_subject: dict[str, StoredTokens] = {}
        self.session_to_subject: dict[str, str] = {}

    async def upsert(self, tokens: StoredTokens, session_id: str | None = None) -> None:
        self.by_subject[tokens.subject] = tokens
        if session_id:
            self.session_to_subject[session_id] = tokens.subject

    async def get_by_session(self, session_id: str) -> StoredTokens | None:
        subject = self.session_to_subject.get(session_id)
        if not subject:
            return None
        return self.by_subject.get(subject)

    async def bind_session(self, subject: str, session_id: str) -> None:
        self.session_to_subject[session_id] = subject

    async def delete_by_session(self, session_id: str) -> None:
        subject = self.session_to_subject.pop(session_id, None)
        if subject:
            self.by_subject.pop(subject, None)


class PostgresTokenStore:
    def __init__(self, database_url: str, key: str) -> None:
        self._database_url = database_url
        self._key = key
        self._pool: asyncpg.Pool | None = None

    async def _conn(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._database_url, min_size=1, max_size=5)
        return self._pool

    async def upsert(self, tokens: StoredTokens, session_id: str | None = None) -> None:
        pool = await self._conn()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chainlit_oauth_tokens
                    (subject, session_id, access_token_enc, refresh_token_enc, expires_at)
                VALUES (
                    $1, $2,
                    pgp_sym_encrypt($3, $4),
                    CASE WHEN $5 IS NULL THEN NULL ELSE pgp_sym_encrypt($5, $4) END,
                    to_timestamp($6)
                )
                ON CONFLICT (subject) DO UPDATE SET
                    session_id = COALESCE(EXCLUDED.session_id, chainlit_oauth_tokens.session_id),
                    access_token_enc = EXCLUDED.access_token_enc,
                    refresh_token_enc = EXCLUDED.refresh_token_enc,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = now()
                """,
                tokens.subject,
                session_id,
                tokens.access_token,
                self._key,
                tokens.refresh_token,
                tokens.expires_at,
            )

    async def get_by_session(self, session_id: str) -> StoredTokens | None:
        pool = await self._conn()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT subject,
                       pgp_sym_decrypt(access_token_enc, $2) AS access_token,
                       CASE WHEN refresh_token_enc IS NULL THEN NULL
                            ELSE pgp_sym_decrypt(refresh_token_enc, $2) END AS refresh_token,
                       extract(epoch FROM expires_at) AS expires_at
                FROM chainlit_oauth_tokens
                WHERE session_id = $1
                """,
                session_id,
                self._key,
            )
        if row is None:
            return None
        return StoredTokens(
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            expires_at=float(row["expires_at"]),
            subject=row["subject"],
        )

    async def bind_session(self, subject: str, session_id: str) -> None:
        pool = await self._conn()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE chainlit_oauth_tokens SET session_id = $1, updated_at = now() WHERE subject = $2",
                session_id,
                subject,
            )

    async def delete_by_session(self, session_id: str) -> None:
        pool = await self._conn()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM chainlit_oauth_tokens WHERE session_id = $1", session_id)


class KeycloakTokenManager:
    def __init__(
        self,
        store: TokenStore,
        *,
        token_url: str = "",
        client_id: str = "",
        client_secret: str = "",
    ) -> None:
        self._store = store
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret

    def tokens_from_response(self, payload: dict, access_token: str | None = None) -> StoredTokens | None:
        token = access_token or payload.get("access_token")
        if not token:
            return None
        claims = jwt_claims(token)
        subject = str(claims.get("sub") or "")
        if not subject:
            return None
        expires_at = float(claims.get("exp") or (time.time() + int(payload.get("expires_in") or 300)))
        return StoredTokens(
            access_token=token,
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            subject=subject,
        )

    async def save_response(
        self, payload: dict, access_token: str | None = None, session_id: str | None = None
    ) -> StoredTokens | None:
        tokens = self.tokens_from_response(payload, access_token)
        if tokens is None:
            return None
        await self._store.upsert(tokens, session_id=session_id)
        return tokens

    async def bind_session(self, subject: str, session_id: str) -> None:
        await self._store.bind_session(subject, session_id)

    async def get_access_token(self, session_id: str, *, force_refresh: bool = False) -> str | None:
        tokens = await self._store.get_by_session(session_id)
        if tokens is None:
            return None
        if not force_refresh and tokens.expires_at > time.time() + 30:
            return tokens.access_token
        if not tokens.refresh_token or not self._token_url:
            return None
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": tokens.refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        if response.status_code >= 400:
            return None
        refreshed = await self.save_response(response.json(), session_id=session_id)
        return None if refreshed is None else refreshed.access_token


def build_token_manager(settings: Settings) -> KeycloakTokenManager:
    if settings.token_store_database_url:
        store: TokenStore = PostgresTokenStore(
            settings.token_store_database_url,
            settings.token_store_key,
        )
    else:
        store = MemoryTokenStore()
    return KeycloakTokenManager(
        store,
        token_url=os.environ.get("OAUTH_GENERIC_TOKEN_URL", ""),
        client_id=os.environ.get("OAUTH_GENERIC_CLIENT_ID", ""),
        client_secret=os.environ.get("OAUTH_GENERIC_CLIENT_SECRET", ""),
    )
