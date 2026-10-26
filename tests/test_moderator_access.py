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
        monkeypatch.setattr('web.viewer.dashboard.get_db', lambda: db)
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
    assert (await client.get('/me/mod/1/notes')).status_code == 403
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    page = await client.get('/me/mod/1/notes')
    assert page.status_code == 200
    assert page.headers['cache-control'] == 'no-store'
    assert '&lt;script&gt;secret&lt;/script&gt;' in page.text
    assert 'Save note' in page.text
    assert (await client.get('/me/mod/3/notes')).status_code == 403
    assert 'channel_user_id' not in session


@pytest.mark.asyncio
async def test_missing_grant_cannot_edit_and_moderator_is_audited(setup):
    client, session, db, note, _ = setup
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
    assert (await client.get('/me/mod/1/notes')).status_code == 200
    await set_grant(db, '1', '2', '', '', 'revoke')
    assert await channels_for_user(db, '2') == []
    assert (await client.get('/me/mod/1/notes')).status_code == 403
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
    assert (await client.get('/me/mod/1/notes')).status_code == 401
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
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    request = SimpleNamespace(session=session)
    assert len(await moderation.mod_bar_channels(request)) == 1
    session['viewer_server_token'] = 'invalid'
    assert await moderation.mod_bar_channels(request) == []


@pytest.mark.asyncio
async def test_no_grant_from_twitch_role_or_admin_session(setup):
    client, session, db, note, _ = setup
    session.update(administrator_id=1, channel_user_id='3')
    assert (await client.get('/me/mod/1/notes')).status_code == 403
    session.clear()
    response = await client.get('/me/mod/1/notes')
    assert response.status_code == 303
    assert response.headers['location'] == '/me/connect'


@pytest.mark.asyncio
async def test_pagination_and_escaped_channel_names(setup):
    client, session, db, note, _ = setup
    await set_grant(db, '1', '2', '<script>channel</script>', 'Moderator', 'edit')
    for i in range(20):
        await manage_note(db, '1', 'create', title=str(i), notes='Note')
    page = await client.get('/me/mod/1/notes')
    assert '?offset=20' in page.text
    assert '&lt;script&gt;channel&lt;/script&gt;' in page.text
    assert (await client.get('/me/mod/1/notes?offset=-1')).status_code == 422
    assert 'Next</a>' not in (await client.get('/me/mod/1/notes?offset=20')).text


@pytest.mark.asyncio
async def test_new_chatter_can_use_mod_bar_without_channel_activity(setup, monkeypatch):
    from web.viewer import routers
    client, session, db, note, _ = setup
    client._transport.app.include_router(routers.router)
    monkeypatch.setattr(routers, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(
        chatter_stats=SimpleNamespace(get_global_profile=AsyncMock(return_value=None)))))
    assert 'Mod Bar' not in (await client.get('/me')).text
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    page = await client.get('/me')
    assert page.status_code == 200
    assert 'Mod Bar' in page.text and 'href="/me/mod/1"' in page.text
    await revoke_viewer_session(db, session['viewer_server_token'])
    assert 'Mod Bar' not in (await client.get('/me')).text


@pytest.mark.asyncio
async def test_access_search_is_owner_only_and_reports_existing_grant(setup):
    client, session, db, note, bot = setup
    assert (await client.get('/channel/access/search?query=moderator')).status_code == 401
    bot.fetch_users.assert_not_awaited()
    session.update(channel_user_id='1')
    await set_grant(db, '1', '2', 'Streamer', 'Moderator', 'edit')
    response = await client.get('/channel/access/search?query=%40Moderator')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['user'] == {'id': '2', 'display_name': 'Moderator', 'permission': 'edit', 'is_owner': False}
    bot.fetch_users.assert_awaited_once_with(logins=['moderator'])
    assert (await client.get('/channel/access/search?query=invalid!')).status_code == 400
    bot.fetch_users.return_value = []
    assert (await client.get('/channel/access/search?query=missing')).status_code == 404


@pytest.mark.asyncio
async def test_selected_account_is_reverified_by_stable_id(setup):
    client, session, db, note, bot = setup
    session.update(channel_user_id='1')
    response = await client.post('/channel/access', data={'csrf_token': 'secret', 'user_id': '2', 'permission': 'edit'})
    assert response.status_code == 303
    bot.fetch_users.assert_awaited_once_with(ids=['2'])
    assert (await channels_for_user(db, '2'))[0]['permission'] == 'edit'
    bot.fetch_users.return_value = []
    assert (await client.post('/channel/access', data={'csrf_token': 'secret', 'user_id': '3', 'permission': 'edit'})).status_code == 404
    assert await channels_for_user(db, '3') == []


@pytest.mark.asyncio
async def test_owner_search_and_runtime_failure(setup):
    client, session, db, note, bot = setup
    session.update(channel_user_id='2')
    assert (await client.get('/channel/access/search?query=moderator')).json()['user']['is_owner'] is True
    assert (await client.post('/channel/access', data={'csrf_token': 'secret', 'user_id': '2', 'permission': 'edit'})).status_code == 400
    bot.fetch_users.side_effect = TimeoutError()
    assert (await client.get('/channel/access/search?query=moderator')).status_code == 503


@pytest.mark.asyncio
async def test_owner_changes_existing_role_and_view_is_rejected(setup):
    client, session, db, note, bot = setup
    session.update(channel_user_id='1')
    await set_grant(db,'1','2','Streamer','Moderator','edit')
    page = await client.get('/channel/access')
    assert 'data-role-select' in page.text and 'role-edit' in page.text
    assert '<option value="view">' not in page.text
    for role in ('super','edit'):
        response = await client.post('/channel/access', data={'csrf_token':'secret','user_id':'2','permission':role}, headers={'Accept':'application/json'})
        assert response.status_code == 200
        assert response.json() == {'permission':role, 'user_id':'2'}
        assert (await channels_for_user(db,'2'))[0]['permission'] == role
    assert (await client.post('/channel/access',data={'csrf_token':'secret','user_id':'2','permission':'view'})).status_code == 400
    with pytest.raises(ValueError):
        await set_grant(db,'1','2','Streamer','Moderator','view')


@pytest.mark.asyncio
async def test_retired_view_grants_are_removed_without_escalating_roles(tmp_path):
    from storage.migrations.core.v071_channel_access import migrate as m71
    from storage.migrations.core.v072_moderator_dashboard import migrate as m72
    from storage.migrations.core.v074_retire_view_role import migrate as m74
    async with asqlite.create_pool(str(tmp_path/'legacy.db')) as db:
        async with db.acquire() as conn:
            await m71(conn)
            await m72(conn)
            for actor, role in [('2','view'),('3','edit'),('4','super')]:
                await conn.execute("INSERT INTO channel_access VALUES ('1', ?, 'Streamer', 'Person', 'dashboard', ?)", (actor,role))
            await m74(conn)
            rows=await conn.fetchall('SELECT user_id, permission FROM channel_access ORDER BY user_id')
            assert [tuple(r) for r in rows]==[('3','edit'),('4','super')]
            import sqlite3
            with pytest.raises(sqlite3.IntegrityError):
                await conn.execute("INSERT INTO channel_access VALUES ('1','2','Streamer','Person','dashboard','view')")


@pytest.mark.asyncio
async def test_mod_bar_uses_cached_streamer_avatars(setup):
    client, session, db, note, bot = setup
    await set_grant(db,'1','2','Streamer','Moderator','edit')
    await set_grant(db,'3','2','Missing image','Moderator','edit')
    bot.services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda:{'1':SimpleNamespace(profile_image_url='https://example.com/streamer.png')}))
    channels=await moderation.mod_bar_channels(SimpleNamespace(session=session))
    assert next(c for c in channels if c['broadcaster_id']=='1')['profile_image_url']=='https://example.com/streamer.png'
    assert next(c for c in channels if c['broadcaster_id']=='3')['profile_image_url'] is None
    bot.fetch_users.assert_not_awaited()
