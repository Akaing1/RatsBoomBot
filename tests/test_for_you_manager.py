import pytest
from tests.test_streamer_workspace import workspace_client
from storage import streamer_workspace as repository
from storage.for_you import notes_page, quotes_page, change_quote
from bot.services.channels.quotes import QuoteService


@pytest.mark.asyncio
async def test_notes_update_one_entry_and_archive_across_streams(workspace_client):
    _, _, db = workspace_client
    initial = await repository.get_workspace(db, 'alice', 'stream:one')
    saved = await repository.update_workspace(db, 'alice', 'notes', notes='First', revision=initial['notes_revision'], note_key='stream:one')
    await repository.update_workspace(db, 'alice', 'notes', notes='Updated', revision=saved['notes_revision'], note_key='stream:one')
    assert len((await notes_page(db, 'alice'))['items']) == 1
    next_stream = await repository.get_workspace(db, 'alice', 'stream:two')
    assert next_stream['notes'] == ''
    with pytest.raises(ValueError):
        await repository.update_workspace(db, 'alice', 'notes', notes='Stale', revision=saved['notes_revision'], note_key='stream:two')
    assert (await notes_page(db, 'alice'))['items'][0]['notes'] == 'Updated'
    assert (await notes_page(db, 'bob'))['items'] == []
    resumed = await repository.get_workspace(db, 'alice', 'stream:one')
    assert resumed['notes'] == 'Updated'


@pytest.mark.asyncio
async def test_quote_identity_survives_chat_deletion_and_manager_is_scoped(workspace_client):
    client, session, db = workspace_client
    service = QuoteService(db)
    await service.add('alice', 'First', 'mod')
    await service.add('alice', 'Second', 'mod')
    second = (await quotes_page(db, 'alice'))['items'][0]
    await service.remove('alice', 1)
    await change_quote(db, 'alice', second['manager_id'], 'Second', 'Edited')
    assert await service.get('alice', 1) == 'Edited'
    with pytest.raises(ValueError):
        await change_quote(db, 'alice', second['manager_id'], 'Second', 'Stale')
    session['channel_user_id'] = 'bob'
    assert (await client.get('/channel/api/for-you/quotes')).json()['items'] == []
    response = await client.post('/channel/api/for-you/quotes', data=dict(csrf_token='secret', action='delete', identity=second['manager_id'], original='Edited'))
    assert response.status_code == 409
    assert await service.get('alice', 1) == 'Edited'
    session['channel_user_id'] = 'alice'
    assert (await client.post('/channel/api/for-you/quotes', data=dict(csrf_token='wrong', action='add', message='No'))).status_code == 403
    response = await client.post('/channel/api/for-you/quotes', data=dict(csrf_token='secret', action='delete', identity=second['manager_id'], original='Edited'))
    assert response.status_code == 200
    assert await service.add('alice', 'New', 'mod') == 1
    assert (await quotes_page(db, 'alice'))['items'][0]['manager_id'] != second['manager_id']


@pytest.mark.asyncio
async def test_notes_and_quotes_pagination(workspace_client):
    client, _, db = workspace_client
    for i in range(21):
        await QuoteService(db).add('alice', f'Quote {i}', 'mod')
    first = (await client.get('/channel/api/for-you/quotes')).json()
    assert len(first['items']) == 20 and first['more']
    last = (await client.get('/channel/api/for-you/quotes?offset=20')).json()
    assert len(last['items']) == 1 and not last['more']
    assert len((await client.get('/channel/api/for-you/quotes?search=Quote%2020')).json()['items']) == 1



@pytest.mark.asyncio
async def test_migration_preserves_existing_notes_and_quotes(tmp_path):
    import asqlite
    from storage.migrations.core.v046_channel_quotes import migrate as quotes
    from storage.migrations.core.v068_streamer_workspace import migrate as workspace
    from storage.migrations.core.v069_for_you_archive import migrate as archive
    from storage.migrations.core.v070_note_management import migrate as management
    async with asqlite.create_pool(str(tmp_path / 'upgrade.db')) as db:
        async with db.acquire() as connection:
            await quotes(connection)
            await workspace(connection)
            await connection.execute("INSERT INTO streamer_workspace (broadcaster_id, notes, notes_revision) VALUES ('alice', 'Keep this', 4)")
            await connection.execute("INSERT INTO channel_quotes (broadcaster_id, number, message, added_by) VALUES ('alice', 1, 'Original', 'mod')")
            await archive(connection)
            await management(connection)
        assert (await notes_page(db, 'alice'))['items'][0]['notes'] == 'Keep this'
        assert (await quotes_page(db, 'alice'))['items'][0]['manager_id']
        state = await repository.get_workspace(db, 'alice', 'stream:new')
        assert state['notes'] == ''
        assert (await notes_page(db, 'alice'))['items'][0]['note_key'] == 'legacy'


def test_for_you_page_renders_notes_and_quotes():
    from web.shared.common import templates
    html = templates.env.get_template('channel/workspace.html').render(active_page='for-you', csrf_token='test', url_for=lambda *a, **k: '/static', deployment_stamp=lambda: 'test')
    assert 'data-workspace-panel="notes"' in html
    assert 'data-workspace-panel="quotes"' in html
    assert 'href="/channel/for-you"' in html


def test_stream_scope_uses_stable_twitch_session(monkeypatch):
    from types import SimpleNamespace
    from web.channel.routers import workspace
    session = SimpleNamespace(stream_id='12345')
    monkeypatch.setattr(workspace, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(stream_logs=SimpleNamespace(get_active_session=lambda channel: session))))
    assert workspace.current_note_key('alice') == 'stream:12345'
    session.stream_id = '67890'
    assert workspace.current_note_key('alice') == 'stream:67890'


@pytest.mark.asyncio
async def test_manager_requires_authentication(workspace_client):
    client, session, _ = workspace_client
    session.clear()
    for path in ('notes', 'quotes'):
        assert (await client.get('/channel/api/for-you/' + path)).status_code == 401
    assert (await client.post('/channel/api/for-you/quotes', data=dict(csrf_token='secret', action='add', message='No'))).status_code == 401
    assert (await client.get('/channel/for-you')).status_code == 303


@pytest.mark.asyncio
async def test_note_titles_order_delete_and_channel_scope(workspace_client):
    from storage.for_you import manage_note
    client, session, db = workspace_client
    first = await manage_note(db, 'alice', 'create', notes='First')
    second = await manage_note(db, 'alice', 'create', notes='Second')
    third = await manage_note(db, 'alice', 'create', notes='Third')
    assert [n['display_name'] for n in (await notes_page(db, 'alice'))['items']] == ['Unnamed note 1', 'Unnamed note 2', 'Unnamed note 3']
    await manage_note(db, 'alice', 'up', third['note_id'], third['revision'])
    assert [n['notes'] for n in (await notes_page(db, 'alice'))['items']] == ['First', 'Third', 'Second']
    renamed = await manage_note(db, 'alice', 'save', first['note_id'], first['revision'], 'Clips', 'Edited')
    assert [n['display_name'] for n in (await notes_page(db, 'alice'))['items']] == ['Clips', 'Unnamed note 1', 'Unnamed note 2']
    with pytest.raises(ValueError):
        await manage_note(db, 'alice', 'delete', first['note_id'], first['revision'])
    session['channel_user_id'] = 'bob'
    assert (await client.get('/channel/api/for-you/notes/' + first['note_id'])).status_code == 404
    assert (await client.post('/channel/api/for-you/notes', data=dict(csrf_token='secret', action='delete', identity=first['note_id'], revision=renamed['revision']))).status_code == 409
    await manage_note(db, 'alice', 'delete', third['note_id'], third['revision'])
    assert [n['display_name'] for n in (await notes_page(db, 'alice'))['items']] == ['Clips', 'Unnamed note 1']
    assert [n['position'] for n in (await notes_page(db, 'alice'))['items']] == [1, 2]


@pytest.mark.asyncio
async def test_manager_and_overview_edits_stay_in_sync(workspace_client):
    from storage.for_you import manage_note
    client, _, db = workspace_client
    state = (await client.get('/channel/api/for-you')).json()
    saved = (await client.post('/channel/api/for-you', data=dict(csrf_token='secret', action='notes', notes='From overview', title='My title', revision=state['notes_revision']))).json()
    item = (await notes_page(db, 'alice'))['items'][0]
    edited = await manage_note(db, 'alice', 'save', item['note_id'], item['revision'], 'Renamed', 'From manager')
    current = (await client.get('/channel/api/for-you')).json()
    assert current['notes'] == 'From manager' and current['title'] == 'Renamed'
    assert (await client.post('/channel/api/for-you', data=dict(csrf_token='secret', action='notes', notes='Stale', revision=saved['notes_revision']))).status_code == 409
    blank = (await client.post('/channel/api/for-you', data=dict(csrf_token='secret', action='notes', title='', notes='From manager', revision=current['notes_revision']))).json()
    assert blank['display_name'] == 'Unnamed note 1'
    await manage_note(db, 'alice', 'delete', item['note_id'], blank['archive_revision'])
    assert (await client.get('/channel/api/for-you')).json()['notes'] == ''
    assert (await client.post('/channel/api/for-you', data=dict(csrf_token='secret', action='notes', notes='Resurrect', revision=blank['notes_revision']))).status_code == 409
    assert (await client.post('/channel/api/for-you/notes', data=dict(csrf_token='wrong', action='create'))).status_code == 403
