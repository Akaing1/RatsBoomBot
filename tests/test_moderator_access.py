from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from storage.channel_access import set_grant, channels_for_user
from storage.for_you import manage_note
from storage.migration_runner import run_migrations
from storage.viewer_sessions import create_viewer_session, revoke_viewer_session
from web.viewer import moderation


@pytest.fixture
async def setup(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'access.db')) as db:
        await run_migrations(db)
        monkeypatch.setattr(moderation, 'get_db', lambda: db)
        bot = SimpleNamespace(fetch_users=AsyncMock(return_value=[SimpleNamespace(id='2', display_name='Moderator')]))
        monkeypatch.setattr(moderation, 'get_bot', lambda: bot)
        token = await create_viewer_session(db, '2')
        session = {'viewer_user_id': '2', 'viewer_server_token': token, 'csrf_token': 'secret'}
        app = FastAPI()
        app.mount('/static', StaticFiles(directory='web/static'), name='static')
        app.mount('/assets', StaticFiles(directory='assets'), name='assets')
        @app.middleware('http')
        async def middleware(request, call_next):
            request.scope['session'] = session.copy()
            return await call_next(request)
        app.include_router(moderation.router)
        note = await manage_note(db, '1', 'create', title='Private', notes='<script>secret</script>')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, session, db, note, bot


def payload(note, **changes):
    return {'csrf_token': 'secret', 'revision': note['revision'], 'title': 'Updated', 'notes': 'Changed', **changes}


@pytest.mark.asyncio
async def test_grant_required_and_other_channel_denied(setup):
    client, session, db, note, _ = setup
    assert (await client.get('/me/mod/1')).status_code == 403
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'view')
    page = await client.get('/me/mod/1')
    assert page.status_code == 200
    assert page.headers['cache-control'] == 'no-store'
    assert '&lt;script&gt;secret&lt;/script&gt;' in page.text
    assert 'Save note' not in page.text
    assert (await client.get('/me/mod/3')).status_code == 403
    assert 'channel_user_id' not in session


@pytest.mark.asyncio
async def test_view_cannot_edit_and_edit_is_audited(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'view')
    path = '/me/mod/1/notes/' + note['note_id']
    assert (await client.post(path, data=payload(note))).status_code == 403
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    assert (await client.post(path, data=payload(note, csrf_token='bad'))).status_code == 403
    assert (await client.post(path, data=payload(note))).status_code == 303
    async with db.acquire() as conn:
        audit = await conn.fetchone("SELECT * FROM channel_access_audit WHERE action = 'notes:save'")
        assert audit['actor_id'] == '2' and audit['broadcaster_id'] == '1'
        saved = await conn.fetchone('SELECT * FROM streamer_notes WHERE note_id = ?', (note['note_id'],))
        assert saved['notes'] == 'Changed'
    conflict = await client.post(path, data=payload(note, notes='Keep my draft'))
    assert conflict.status_code == 409
    assert 'Keep my draft' in conflict.text


@pytest.mark.asyncio
async def test_revocation_blocks_open_page_save_and_removes_channel(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    assert (await client.get('/me/mod/1')).status_code == 200
    await set_grant(db, '1', '2', '', '', 'revoke')
    assert await channels_for_user(db, '2') == []
    assert (await client.get('/me/mod/1')).status_code == 403
    assert (await client.post('/me/mod/1/notes/' + note['note_id'], data=payload(note))).status_code == 403


@pytest.mark.asyncio
async def test_foreign_note_cannot_be_overwritten(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '3', '2', 'Other', 'Moderator', 'edit')
    assert (await client.post('/me/mod/3/notes/' + note['note_id'], data=payload(note))).status_code == 409
    async with db.acquire() as conn:
        row = await conn.fetchone('SELECT notes FROM streamer_notes WHERE note_id = ?', (note['note_id'],))
        assert row['notes'] == '<script>secret</script>'


@pytest.mark.asyncio
async def test_revoked_signin_cannot_read_or_write(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    await revoke_viewer_session(db, session['viewer_server_token'])
    assert (await client.get('/me/mod/1')).status_code == 401
    assert (await client.post('/me/mod/1/notes/' + note['note_id'], data=payload(note))).status_code == 401


@pytest.mark.asyncio
async def test_only_owner_can_manage_grants_and_user_id_is_resolved(setup):
    client, session, db, note, bot = setup
    form = {'csrf_token': 'secret', 'login': 'moderator', 'permission': 'edit', 'user_id': '999', 'broadcaster_id': '999'}
    assert (await client.post('/channel/access', data=form)).status_code == 401
    session.update(channel_user_id='1', channel_user_display_name='Streamer')
    assert (await client.post('/channel/access', data={**form, 'csrf_token': 'bad'})).status_code == 403
    assert (await client.post('/channel/access', data=form)).status_code == 303
    bot.fetch_users.assert_awaited_once_with(logins=['moderator'])
    grants = await channels_for_user(db, '2')
    assert grants[0]['broadcaster_id'] == '1'
    assert await channels_for_user(db, '999') == []
    page = await client.get('/channel/access')
    assert 'Moderator' in page.text and page.status_code == 200
    assert (await client.post('/channel/access', data={'csrf_token': 'secret', 'user_id': '2', 'permission': 'revoke'})).status_code == 303
    assert await channels_for_user(db, '2') == []


@pytest.mark.asyncio
async def test_mod_bar_requires_valid_session(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'view')
    request = SimpleNamespace(session=session)
    assert len(await moderation.mod_bar_channels(request)) == 1
    session['viewer_server_token'] = 'invalid'
    assert await moderation.mod_bar_channels(request) == []


@pytest.mark.asyncio
async def test_no_grant_from_twitch_role_or_admin_session(setup):
    client, session, db, note, _ = setup
    session.update(administrator_id=1, channel_user_id='3')
    assert (await client.get('/me/mod/1')).status_code == 403
    session.clear()
    response = await client.get('/me/mod/1')
    assert response.status_code == 303
    assert response.headers['location'] == '/me/connect'


@pytest.mark.asyncio
async def test_pagination_and_escaped_channel_names(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '1', '2', '<script>channel</script>', 'Moderator', 'view')
    for i in range(20):
        await manage_note(db, '1', 'create', title=str(i), notes='Note')
    page = await client.get('/me/mod/1')
    assert '?offset=20' in page.text
    assert '&lt;script&gt;channel&lt;/script&gt;' in page.text
    assert (await client.get('/me/mod/1?offset=-1')).status_code == 422
    assert 'Next</a>' not in (await client.get('/me/mod/1?offset=20')).text


@pytest.mark.asyncio
async def test_new_chatter_can_use_mod_bar_without_channel_activity(setup, monkeypatch):
    from web.viewer import routers
    client, session, db, note, _ = setup
    client._transport.app.include_router(routers.router)
    monkeypatch.setattr(routers, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(
        chatter_stats=SimpleNamespace(get_global_profile=AsyncMock(return_value=None)))))
    assert 'Mod Bar' not in (await client.get('/me')).text
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'view')
    page = await client.get('/me')
    assert page.status_code == 200
    assert 'Mod Bar' in page.text and 'href="/me/mod/1"' in page.text
    await revoke_viewer_session(db, session['viewer_server_token'])
    assert 'Mod Bar' not in (await client.get('/me')).text
