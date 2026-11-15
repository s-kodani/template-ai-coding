"""Bound persistence retries for the pinned upstream SSO refresh implementation."""
from __future__ import annotations

import asyncio


class TokenPersistenceError(RuntimeError):
    """A refreshed token could not be persisted; require reauthentication on failure."""


async def persist_refreshed_session(sessions, session_id: str, token: dict):
    # Upstream hides storage exceptions behind None. Retry only storage, never the
    # provider exchange: a successful refresh may already have rotated its token.
    for attempt in range(3):
        if attempt:
            await asyncio.sleep(0.1 * attempt)
        updated = await sessions.update_session_by_id(session_id, token)
        if updated is not None:
            return updated
    raise TokenPersistenceError("Refreshed OAuth token could not be saved; sign in again")
