from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


@dataclass
class CacheEntry:
    token: str
    expires_at: float


class TokenCache:
    def __init__(self, max_ttl_seconds: int = 300) -> None:
        self._max_ttl = max_ttl_seconds
        self._entries: dict[str, CacheEntry] = {}

    def _key(self, source_token: str, server_id: str, scopes: list[str]) -> str:
        material = f"{source_token}\0{server_id}\0{','.join(scopes)}"
        return hashlib.sha256(material.encode()).hexdigest()

    def get(self, source_token: str, server_id: str, scopes: list[str]) -> str | None:
        key = self._key(source_token, server_id, scopes)
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= time.time():
            self._entries.pop(key, None)
            return None
        return entry.token

    def put(
        self,
        source_token: str,
        server_id: str,
        scopes: list[str],
        token: str,
        expires_at: float,
    ) -> None:
        ttl = min(self._max_ttl, max(0, expires_at - time.time() - 5))
        if ttl <= 0:
            return
        self._entries[self._key(source_token, server_id, scopes)] = CacheEntry(
            token=token, expires_at=time.time() + ttl
        )
