"""Execute the pinned upstream refresh methods with a real SQLite storage boundary."""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from open_webui_ext.patch import patch_source

NOW = 1_800_000_000


class Clock(datetime):
    @classmethod
    def now(cls):
        return cls.fromtimestamp(NOW)


class Sessions:
    """Only the upstream DB boundary is substituted; SQL writes use separate connections."""

    def __init__(self, path):
        self.path = path
        self.updates = 0
        self.deletes = 0
        self.failed_write = asyncio.Event()
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY, token TEXT)')
            db.execute('INSERT INTO sessions VALUES (?, ?)', ('s', json.dumps({
                'access_token': 'old', 'expires_at': NOW + 300,
            })))

    async def get_session_by_id(self, session_id):
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT token FROM sessions WHERE id=?', (session_id,)).fetchone()
        if row:
            token = json.loads(row[0])
            return SimpleNamespace(id=session_id, provider='oidc', token=token,
                                   expires_at=token['expires_at'])

    async def get_session_by_id_and_user_id(self, session_id, user_id):
        return await self.get_session_by_id(session_id) if user_id == 'u' else None

    async def update_session_by_id(self, session_id, token):
        self.updates += 1

        def write():
            try:
                with sqlite3.connect(self.path, timeout=.01) as db:
                    db.execute('UPDATE sessions SET token=? WHERE id=?',
                               (json.dumps(token), session_id))
                return True
            except sqlite3.OperationalError:
                return False  # Upstream model swallows the DB exception and returns None.

        if await asyncio.to_thread(write):
            return await self.get_session_by_id(session_id)
        self.failed_write.set()

    async def delete_session_by_id(self, session_id):
        self.deletes += 1
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM sessions WHERE id=?', (session_id,))


@pytest.fixture
def runtime(tmp_path):
    source = Path('tests/fixtures/openwebui_oauth_manager.txt').read_text()
    source = patch_source('utils/oauth.py', source)
    store = Sessions(tmp_path / 'oauth.db')
    namespace = {
        'asyncio': asyncio, 'datetime': Clock, 'timedelta': timedelta,
        'OAuthSessions': store, 'log': logging.getLogger('oauth-test'),
        'jwt': SimpleNamespace(decode=lambda *a, **kw: {'exp': NOW + 20}),
    }
    exec(compile(source, 'upstream-oauth.py', 'exec'), namespace)  # noqa: S102 — audited fixture
    manager = namespace['OAuthManager']()
    manager.app = SimpleNamespace(state=SimpleNamespace(redis=None))
    manager._refresh_locks = {}
    manager.refreshes = 0

    async def refresh(session):
        manager.refreshes += 1
        await asyncio.sleep(0)
        return {'access_token': f'new-{manager.refreshes}', 'expires_at': NOW + 300}

    manager._perform_token_refresh = refresh
    return manager, store


@pytest.mark.parametrize('remaining, refresh', [(300, False), (31, False), (30, True),
                                               (29, True), (0, True), (-1, True)])
async def test_token_expiry_boundary(runtime, remaining, refresh):
    manager, store = runtime
    await store.update_session_by_id('s', {'access_token': 'old', 'expires_at': NOW + remaining})
    token = await manager.get_oauth_token('u', 's')
    assert token['access_token'] == ('new-1' if refresh else 'old')
    assert manager.refreshes == int(refresh)


async def test_parallel_requests_share_refresh_and_reuse_saved_token(runtime):
    manager, store = runtime
    await store.update_session_by_id('s', {'access_token': 'old', 'expires_at': NOW})
    tokens = await asyncio.gather(*(manager.get_oauth_token('u', 's') for _ in range(12)))
    assert all(token['access_token'] == 'new-1' for token in tokens)
    assert (await manager.get_oauth_token('u', 's'))['access_token'] == 'new-1'
    assert manager.refreshes == 1


async def test_shorter_id_token_expiry_and_explicit_refresh_are_honored(runtime):
    manager, store = runtime
    await store.update_session_by_id('s', {'access_token': 'old', 'id_token': 'test',
                                         'expires_at': NOW + 300})
    assert (await manager.get_oauth_token('u', 's'))['access_token'] == 'new-1'
    assert (await manager.get_oauth_token('u', 's', force_refresh=True))['access_token'] == 'new-2'


async def test_temporary_sqlite_writer_lock_retries_storage_without_repeating_refresh(runtime):
    manager, store = runtime
    writer = sqlite3.connect(store.path)
    writer.execute('BEGIN IMMEDIATE')
    try:
        task = asyncio.create_task(manager.get_oauth_token('u', 's', force_refresh=True))
        await asyncio.wait_for(store.failed_write.wait(), timeout=2)
        writer.rollback()
        token = await task
        assert token['access_token'] == 'new-1'
        assert (await store.get_session_by_id('s')).token == token
        assert manager.refreshes == 1
        assert store.updates >= 2
    finally:
        writer.close()


async def test_persistent_lock_fails_closed_without_deleting_session_or_secondary_error(runtime, caplog):
    manager, store = runtime
    writer = sqlite3.connect(store.path)
    writer.execute('BEGIN IMMEDIATE')
    try:
        token = await manager.get_oauth_token('u', 's', force_refresh=True)
        assert token is None
        assert store.deletes == 0
        assert store.updates == 3
        assert manager.refreshes == 1
        assert 'NoneType' not in caplog.text
        assert (await store.get_session_by_id('s')).token['access_token'] == 'old'
    finally:
        writer.rollback()
        writer.close()


async def test_missing_or_other_users_session_does_not_refresh(runtime):
    manager, _ = runtime
    assert await manager.get_oauth_token('other', 's') is None
    assert await manager.get_oauth_token('u', 'missing') is None
    assert manager.refreshes == 0


async def test_provider_rejection_keeps_upstream_session_invalidation(runtime):
    manager, store = runtime

    async def rejected(session):
        return None

    manager._perform_token_refresh = rejected
    assert await manager.get_oauth_token('u', 's', force_refresh=True) is None
    assert await store.get_session_by_id('s') is None


async def test_sso_patch_does_not_change_mcp_provider_refresh():
    source = Path('tests/fixtures/openwebui_oauth_manager.txt').read_text()
    source += """
class MCPProvider:
    async def refresh(self, session, refreshed_token):
        if session:
            if refreshed_token:
                session = await OAuthSessions.update_session_by_id(session.id, refreshed_token)
        return session
"""

    async def unavailable(*args):
        return None

    namespace = {'OAuthSessions': SimpleNamespace(update_session_by_id=unavailable)}
    patched = patch_source('utils/oauth.py', source)
    exec(compile(patched, 'upstream-oauth.py', 'exec'), namespace)  # noqa: S102 — audited fixture
    # MCP-provider persistence keeps its upstream None contract, without SSO retries/errors.
    assert await namespace['MCPProvider']().refresh(SimpleNamespace(id='s'), {'test': True}) is None
