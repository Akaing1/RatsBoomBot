import asqlite
import httpx
import pytest
from fastapi import FastAPI

from storage import streamer_workspace as repository
from storage.migration_runner import run_migrations
from web.channel.routers import workspace


@pytest.fixture
async def workspace_client(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'workspace.db')) as db:
        await run_migrations(db)
        monkeypatch.setattr(workspace, 'get_db', lambda: db)
        session = {'channel_user_id': 'alice', 'csrf_token': 'secret'}
        app = FastAPI()
        @app.middleware('http')
        async def add_session(request, call_next):
            request.scope['session'] = session.copy()
            return await call_next(request)
        app.include_router(workspace.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, session, db


@pytest.mark.asyncio
async def test_private_notes_persist_and_stale_edits_cannot_overwrite(workspace_client):
    client, session, db = workspace_client
    assert (await client.get('/channel/api/for-you')).json()['notes'] == ''
    response = await client.post('/channel/api/for-you', data={
        'csrf_token': 'secret', 'action': 'notes', 'notes': '<script>private</script>\npizza', 'revision': 0,
        'broadcaster_id': 'bob',
    })
    assert response.status_code == 200
    assert response.json()['notes_revision'] == 1
    assert response.headers['cache-control'] == 'no-store'
    stale = await client.post('/channel/api/for-you', data={'csrf_token': 'secret', 'action': 'notes', 'notes': 'lost', 'revision': 0})
    assert stale.status_code == 409
    assert (await repository.get_workspace(db, 'alice'))['notes'] == '<script>private</script>\npizza'
    session['channel_user_id'] = 'bob'
    assert (await client.get('/channel/api/for-you')).json()['notes'] == ''
    session['channel_user_id'] = 'alice'
    assert (await client.get('/channel/api/for-you')).json()['notes_revision'] == 1


@pytest.mark.asyncio
async def test_auth_csrf_and_validation(workspace_client):
    client, session, db = workspace_client
    session.clear()
    assert (await client.get('/channel/api/for-you')).status_code == 401
    assert (await client.post('/channel/api/for-you', data={'csrf_token': 'secret', 'action': 'notes'})).status_code == 401
    session.update(channel_user_id='alice', csrf_token='secret')
    assert (await client.post('/channel/api/for-you', data={'csrf_token': 'wrong', 'action': 'notes'})).status_code == 403
    for data in [dict(action='start', minutes=0, label='pizza'), dict(action='start', minutes=1, label='   '), dict(action='bad')]:
        assert (await client.post('/channel/api/for-you', data={'csrf_token': 'secret', **data})).status_code == 400
    for data in [dict(action='start', minutes=10081, label='pizza'), dict(action='start', minutes='1.5', label='pizza'), dict(action='notes', notes='a' * 20001)]:
        assert (await client.post('/channel/api/for-you', data={'csrf_token': 'secret', **data})).status_code == 422
    assert (await repository.get_workspace(db, 'alice'))['timer_id'] is None


@pytest.mark.asyncio
async def test_timer_deadline_survives_refresh_and_stale_dismissal(workspace_client, monkeypatch):
    client, session, db = workspace_client
    monkeypatch.setattr(repository.time, 'time', lambda: 1000)
    async def post(**data):
        return await client.post('/channel/api/for-you', data={'csrf_token': 'secret', **data})
    first = (await post(action='start', label='Get pizza', minutes=20)).json()
    assert first['timer_due_at'] == 2200
    assert (await post(action='start', label='Wrong tab', minutes=5)).status_code == 409
    assert (await post(action='notes', notes='Reminder notes', revision=0)).status_code == 200
    assert (await client.get('/channel/api/for-you')).json()['timer_id'] == first['timer_id']
    monkeypatch.setattr(repository.time, 'time', lambda: 2300)
    overdue = (await client.get('/channel/api/for-you')).json()
    assert overdue['server_now'] > overdue['timer_due_at']
    second = (await post(action='start', label='Tea', minutes=1, timer_id=first['timer_id'])).json()
    assert (await post(action='clear', timer_id=first['timer_id'])).status_code == 409
    assert (await client.get('/channel/api/for-you')).json()['timer_id'] == second['timer_id']
    assert (await post(action='clear', timer_id=second['timer_id'])).json()['timer_id'] is None
    assert (await client.get('/channel/api/for-you')).json()['notes'] == 'Reminder notes'


@pytest.mark.asyncio
async def test_state_survives_database_reopen(tmp_path):
    path = str(tmp_path / 'persist.db')
    async with asqlite.create_pool(path) as db:
        await run_migrations(db)
        await repository.update_workspace(db, 'alice', 'notes', notes='Next stream')
        timer = await repository.update_workspace(db, 'alice', 'start', minutes=20, label='Pizza')
    async with asqlite.create_pool(path) as db:
        await run_migrations(db)
        actual = await repository.get_workspace(db, 'alice')
        assert actual['notes'] == 'Next stream'
        assert actual['timer_id'] == timer['timer_id']
        assert actual['timer_due_at'] == timer['timer_due_at']
