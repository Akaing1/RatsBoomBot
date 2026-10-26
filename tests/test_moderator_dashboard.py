from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit
import asqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from storage.channel_access import set_grant
from storage.viewer_sessions import create_viewer_session, revoke_viewer_session
from storage.migration_runner import run_migrations
from web.channel.routers import dashboard as owner
from web.viewer import dashboard, moderation, twitch_actions, routers as viewer
from web.shared.oauth import TwitchTokenResponse, TwitchUser


@pytest.fixture
async def env(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'mod.db')) as db:
        await run_migrations(db)
        token = await create_viewer_session(db, '2')
        session = {'viewer_user_id': '2', 'viewer_user_display_name': 'Alice', 'viewer_server_token': token,
            'channel_user_id': '99', 'csrf_token': 'secret'}
        broadcaster = SimpleNamespace(id='1', name='Streamer', login='streamer', profile_image_url='',
            is_live=False, stream_started_at=None, offline_since=None)
        live = SimpleNamespace(clear_chat=Mock(), get_youtube_state=Mock(return_value={'connected': True}),
            get_or_create_widget_token=AsyncMock(), get_pinned_message=Mock(return_value=None),
            find_message=Mock(return_value={'id':'twitch:abc', 'message':'hello'}), pin_message=AsyncMock(),
            clear_pinned_message=AsyncMock(), remove_message=AsyncMock(), resolve_automod_message=Mock())
        features = SimpleNamespace(is_enabled=Mock(return_value=False),
            get_profile_features=Mock(return_value={}), get_channel_features=Mock(return_value={__import__("bot.profiles", fromlist=["FeatureName"]).FeatureName.POINTS: SimpleNamespace(effective_enabled=True, override_enabled=True, blocked_by_profile=False, blocked_by_globals=False)}),
            get_global_groups=Mock(return_value={}), get_global_commands=Mock(return_value={}),
            set_enabled=AsyncMock(return_value=SimpleNamespace(effective_enabled=True)))
        services = SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {'1': broadcaster}, refresh_live_statuses=AsyncMock()),
            live_chat=live, broadcaster_settings=SimpleNamespace(get_settings=AsyncMock(return_value=SimpleNamespace(follow_raid=True))),
            points=SimpleNamespace(get_gambling_loss_total=AsyncMock(return_value=0)), features=features,
            viewer_queue=SimpleNamespace(is_queue_open=lambda channel: False, list_queue=lambda channel: [], size=lambda channel: 0),
            profile_settings=SimpleNamespace(get_setting_groups=Mock(return_value={})),
            chat_identity=SimpleNamespace(get_state=Mock(side_effect=AssertionError('Owner identity must stay private'))))
        bot = SimpleNamespace(services=services, tokens={}, _http=SimpleNamespace(request_json=AsyncMock(return_value={'data':[]})),
            create_partialuser=Mock(), fetch_users=AsyncMock(return_value=[SimpleNamespace(id='3', display_name='Target')]))
        for module in [dashboard, moderation, twitch_actions]:
            monkeypatch.setattr(module, 'get_db', lambda: db)
        for module in [owner, dashboard, moderation]:
            monkeypatch.setattr(module, 'get_bot', lambda: bot)
        for name,value in [('get_redemption_dashboard_data',{'feed':[], 'mod_actions':[], 'automod':[]}),
            ('get_ad_status',{'state':'idle','label':'No ad scheduled'}), ('get_dashboard_header_stats',[]),
            ('get_twitch_channel_metadata',{'title':'Test stream','game':'Just Chatting','box_art_url':''})]:
            monkeypatch.setattr(owner,name,AsyncMock(return_value=value))
        monkeypatch.setattr(owner,'get_queue_members',lambda services,channel: [])
        monkeypatch.setattr(owner,'get_protected_user_rows',AsyncMock(return_value=[]))
        monkeypatch.setattr(owner,'get_active_profile',lambda channel: SimpleNamespace(points=SimpleNamespace(command_alias='points')))
        app = FastAPI()
        app.mount('/static', StaticFiles(directory='web/static'), name='static')
        app.mount('/assets', StaticFiles(directory='assets'), name='assets')
        @app.middleware('http')
        async def middleware(request, call_next):
            request.scope['session'] = session
            return await call_next(request)
        app.include_router(owner.router)
        app.include_router(dashboard.router)
        app.include_router(moderation.router)
        app.include_router(viewer.router)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            yield client, session, db, bot


@pytest.mark.asyncio
async def test_overview_view_role_shows_feeds_and_hides_owner_controls(env):
    client, session, db, bot = env
    assert (await client.get('/me/mod/1')).status_code == 403
    await set_grant(db,'1','2','Streamer','Alice','view')
    page = await client.get('/me/mod/1')
    assert page.status_code == 200
    assert page.headers['cache-control'] == 'no-store'
    for text in ['Combined Chat','Mod actions','Redeems','AutoMod','data-stream-player','data-stream-url="/me/mod/1/api/chat/stream']:
        assert text in page.text
    assert 'data-raid-browser-open' not in page.text
    assert 'data-raid-browser data-' not in page.text
    assert 'data-mod-note-open' in page.text
    assert 'data-predictions' not in page.text
    assert 'data-queue-action="clear"' not in page.text
    assert 'data-ad-action="run-90"' not in page.text
    assert 'data-moderation-url=' not in page.text
    assert 'data-youtube-connected="false"' in page.text
    assert 'contenteditable="false"' in page.text
    assert 'href="/me/mod/1/settings"' not in page.text
    assert 'data-channel-root="/me/mod/1"' in page.text
    assert session['channel_user_id'] == '99'
    assert owner.get_redemption_dashboard_data.call_args.args[1] == '1'


@pytest.mark.asyncio
async def test_role_boundaries_are_enforced_on_every_endpoint(env):
    client, session, db, bot = env
    await set_grant(db,'1','2','Streamer','Alice','view')
    for path in ['/settings','/protected-users/search?query=alice','/viewer-queue/blacklist']:
        assert (await client.get('/me/mod/1'+path)).status_code == 403
    for path in ['/customization','/features/toggles','/api/viewer-queue/action','/api/ads/action','/api/channel-metadata']:
        response = await client.post('/me/mod/1'+path,data={'csrf_token':'secret','setting_name':'x','action':'enable', 'toggle_type':'feature','toggle_name':'points'})
        assert response.status_code == 403, (path,response.text)
    for path in ['/api/raid-browser','/access','/youtube/connect','/custom-bot/connect','/api/for-you/clips']:
        assert (await client.get('/me/mod/1'+path)).status_code == 404
    assert (await client.get('/me/mod/3')).status_code == 403


@pytest.mark.asyncio
async def test_super_settings_hide_connections_and_use_actor_audit(env):
    client, session, db, bot = env
    await set_grant(db,'1','2','Streamer','Alice','edit')
    assert (await client.get('/me/mod/1/settings')).status_code == 403
    await set_grant(db,'1','2','Streamer','Alice','super')
    page = await client.get('/me/mod/1/settings')
    assert page.status_code == 200
    assert '/me/mod/1/features/toggles' in page.text
    assert 'settings-tab-connections' not in page.text
    assert 'YouTube chat connection' not in page.text
    assert '/widgets/chat/' not in page.text
    bot.services.live_chat.get_or_create_widget_token.assert_not_awaited()
    response = await client.post('/me/mod/1/features/toggles', data={'csrf_token':'secret', 'toggle_type':'feature','toggle_name':'points','action':'enable'})
    assert response.status_code == 303
    assert response.headers['location'].startswith('/me/mod/1/settings?')
    assert bot.services.features.set_enabled.call_args.args[-1] == 'moderator:2'
    assert bot.services.features.set_enabled.call_args.args[0] == '1'
    await set_grant(db,'1','2','','','revoke')
    assert (await client.get('/me/mod/1/settings')).status_code == 403
    assert (await client.post('/me/mod/1/features/toggles',data={'csrf_token':'secret','toggle_type':'feature','toggle_name':'points','action':'enable'})).status_code == 403


@pytest.mark.asyncio
async def test_chat_uses_actor_never_owner_or_supplied_sender(env, monkeypatch):
    client,session,db,bot=env
    await set_grant(db,'1','2','Streamer','Alice','view')
    send=AsyncMock(return_value={'data':[{'is_sent':True,'message_id':'abc'}]})
    monkeypatch.setattr(dashboard,'user_request',send)
    response=await client.post('/me/mod/1/api/chat/send',data={'csrf_token':'secret','message':'hello','target':'twitch','sender_id':'99','broadcaster_id':'99','reply_parent_message_id':'twitch:parent'})
    assert response.status_code==200
    assert send.call_args.args[1]=='2'
    assert send.call_args.kwargs['body']=={'broadcaster_id':'1','sender_id':'2','message':'hello','reply_parent_message_id':'parent'}
    assert (await client.post('/me/mod/1/api/chat/send',data={'csrf_token':'secret','message':'hello','target':'both'})).status_code==400
    assert (await client.post('/me/mod/1/api/chat/send',data={'csrf_token':'bad','message':'hello'})).status_code==403
    assert (await client.post('/me/mod/1/api/chat/send',data={'csrf_token':'secret','message':'/clear'})).status_code==403
    bot.create_partialuser.assert_not_called()


@pytest.mark.asyncio
async def test_predictions_are_role_checked_channel_scoped_and_audited(env, monkeypatch):
    client,session,db,bot=env
    await set_grant(db,'1','2','Streamer','Alice','view')
    action={'csrf_token':'secret','action':'create','title':'Win?','outcomes':'Yes\nNo','window':'60','broadcaster_id':'99'}
    assert (await client.post('/me/mod/1/api/predictions',data=action)).status_code==403
    await set_grant(db,'1','2','Streamer','Alice','edit')
    calls=AsyncMock(return_value={'data':[{'id':'p','broadcaster_id':'1','outcomes':[{'id':'yes'},{'id':'no'}]}]})
    monkeypatch.setattr(dashboard,'prediction_request',calls)
    assert (await client.post('/me/mod/1/api/predictions',data={**action,'csrf_token':'bad'})).status_code==403
    assert (await client.post('/me/mod/1/api/predictions',data=action)).status_code==200
    assert calls.call_args.args==('1','POST')
    assert calls.call_args.kwargs['body']['broadcaster_id']=='1'
    assert calls.call_args.kwargs['body']['outcomes']==[{'title':'Yes'},{'title':'No'}]
    assert (await client.post('/me/mod/1/api/predictions',data={**action,'outcomes':'Only one'})).status_code==400
    assert (await client.post('/me/mod/1/api/predictions',data={'csrf_token':'secret','action':'resolve','prediction_id':'p','winning_outcome_id':'foreign'})).status_code==400
    assert (await client.post('/me/mod/1/api/predictions',data={'csrf_token':'secret','action':'resolve','prediction_id':'p','winning_outcome_id':'yes'})).status_code==200
    assert calls.call_args.kwargs['body']=={'broadcaster_id':'1','id':'p','status':'RESOLVED','winning_outcome_id':'yes'}
    async with db.acquire() as conn:
        row=await conn.fetchone("SELECT * FROM channel_access_audit WHERE actor_id='2' AND action LIKE '%change_prediction'")
        assert row['broadcaster_id']=='1'
    await set_grant(db,'1','2','','','revoke')
    assert (await client.get('/me/mod/1/api/predictions')).status_code==403


@pytest.mark.asyncio
async def test_native_moderation_never_falls_back_to_broadcaster(env,monkeypatch):
    client,session,db,bot=env
    await set_grant(db,'1','2','Streamer','Alice','edit')
    calls=AsyncMock(return_value={})
    monkeypatch.setattr(dashboard,'user_request',calls)
    form={'csrf_token':'secret','action':'delete','message_id':'twitch:abc','moderator_id':'99'}
    assert (await client.post('/me/mod/1/api/chat/moderate',data=form)).status_code==200
    assert calls.call_args.args[1:]==('2','DELETE','moderation/chat')
    assert calls.call_args.kwargs['params']=={'broadcaster_id':'1','moderator_id':'2','message_id':'abc'}
    assert (await client.post('/me/mod/1/api/chat/send',data={'csrf_token':'secret','message':'/timeout target 30 reason'})).status_code==200
    assert calls.call_args.kwargs['body']=={'data':{'user_id':'3','duration':30,'reason':'reason'}}
    assert calls.call_args.kwargs['params']['moderator_id']=='2'
    assert (await client.post('/me/mod/1/api/chat/send',data={'csrf_token':'secret','message':'/mod target'})).status_code==400
    assert (await client.post('/me/mod/1/api/automod/action',data={'csrf_token':'secret','action':'approve','message_id':'a'})).status_code==200
    assert calls.call_args.kwargs['body']['user_id']=='2'
    await set_grant(db,'1','2','Streamer','Alice','view')
    assert (await client.post('/me/mod/1/api/chat/moderate',data=form)).status_code==403


@pytest.mark.asyncio
async def test_oauth_is_identity_bound_replay_safe_and_does_not_onboard(env,monkeypatch):
    client,session,db,bot=env
    await set_grant(db,'1','2','Streamer','Alice','edit')
    start=await client.get('/me/mod/1/connect')
    query=parse_qs(urlsplit(start.headers['location']).query)
    assert 'user:write:chat' in query['scope'][0]
    assert 'moderator:manage:chat_messages' in query['scope'][0]
    assert 'channel:manage:predictions' not in query['scope'][0]
    assert 'channel:bot' not in query['scope'][0]
    state=query['state'][0]
    exchange=AsyncMock(return_value=TwitchTokenResponse('mod-secret','mod-refresh',3600,list(twitch_actions.MOD_SCOPES),'bearer'))
    fetch=AsyncMock(return_value=TwitchUser('99','wrong','Wrong'))
    monkeypatch.setattr(twitch_actions,'exchange_code_for_token',exchange)
    monkeypatch.setattr(twitch_actions,'fetch_twitch_user',fetch)
    result=await client.get('/oauth/viewer/connect',params={'code':'code','state':state})
    assert result.status_code==400
    async with db.acquire() as conn:
        assert await conn.fetchone('SELECT * FROM moderator_twitch_tokens') is None
    start=await client.get('/me/mod/1/connect')
    state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    fetch.return_value=TwitchUser('2','alice','Alice')
    result=await client.get('/oauth/viewer/connect',params={'code':'code','state':state})
    assert result.status_code==303 and result.headers['location'].startswith('/me/mod/1?')
    assert (await client.get('/oauth/viewer/connect',params={'code':'code','state':state})).status_code==400
    assert 'mod-secret' not in str(session) and 'mod-refresh' not in str(session)
    assert session['viewer_user_id']=='2' and session['channel_user_id']=='99'
    async with db.acquire() as conn:
        assert (await conn.fetchone('SELECT user_id FROM moderator_twitch_tokens'))['user_id']=='2'
        assert await conn.fetchone("SELECT * FROM tokens WHERE user_id='2'") is None
    start=await client.get('/me/mod/1/connect')
    state=parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    await set_grant(db,'1','2','','','revoke')
    exchange.reset_mock()
    assert (await client.get('/oauth/viewer/connect',params={'code':'code','state':state})).status_code==403
    exchange.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_stream_rechecks_access_and_unsubscribes_on_revocation(env):
    import asyncio
    from web.shared.live_chat import stream_chat_events
    client,session,db,bot=env
    await set_grant(db,'1','2','Streamer','Alice','view')
    queue=asyncio.Queue()
    live=SimpleNamespace(subscribe=Mock(return_value=queue),unsubscribe=Mock(),history=Mock(return_value=[]))
    scope={'type':'http','path':'/me/mod/1/api/chat/stream','method':'GET','headers':[], 'session':session}
    request=Request(scope)
    await dashboard.authorize(request,'1')
    async def check():
        await dashboard.authorize(request,'1')
    request.state.check_channel_access=check
    request.is_disconnected=AsyncMock(return_value=False)
    stream=stream_chat_events(request,live,'1','both')
    assert 'retry:' in await anext(stream)
    assert 'history-complete' in await anext(stream)
    await set_grant(db,'1','2','','','revoke')
    await queue.put({'event':'chat-clear'})
    assert 'access-revoked' in await anext(stream)
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    live.unsubscribe.assert_called_once_with('1',queue)


@pytest.mark.asyncio
async def test_token_transport_refreshes_only_on_401_without_leaking_credentials(env,monkeypatch):
    client,session,db,bot=env
    await twitch_actions.save_credentials(db,'2',TwitchTokenResponse('old-secret','refresh-secret',3600,['user:write:chat'],'bearer'))
    calls=[]
    async def handler(request):
        calls.append(request)
        if request.url.host=='id.twitch.tv':
            return httpx.Response(200,json={'access_token':'new-secret','refresh_token':'new-refresh'})
        if request.headers['authorization']=='Bearer old-secret':
            return httpx.Response(401,json={'message':'expired'})
        return httpx.Response(200,json={'data':[{'is_sent':True,'message_id':'ok'}]})
    original=httpx.AsyncClient
    monkeypatch.setattr(twitch_actions.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    result=await twitch_actions.user_request(db,'2','POST','chat/messages',body={'sender_id':'2','broadcaster_id':'1','message':'hi'})
    assert result['data'][0]['is_sent'] is True
    assert len(calls)==3
    assert calls[-1].headers['authorization']=='Bearer new-secret'
    async with db.acquire() as conn:
        assert (await conn.fetchone("SELECT access_token FROM moderator_twitch_tokens WHERE user_id='2'"))['access_token']=='new-secret'
    calls.clear()
    async def failure(request):
        calls.append(request)
        return httpx.Response(403,json={'message':'internal details old-secret'})
    monkeypatch.setattr(twitch_actions.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(failure),**kwargs))
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await twitch_actions.user_request(db,'2','POST','chat/messages',body={})
    assert error.value.status_code==403 and 'old-secret' not in error.value.detail
    assert len(calls)==1


@pytest.mark.asyncio
async def test_migration_preserves_existing_roles_without_super_escalation(tmp_path):
    from storage.migrations.core.v071_channel_access import migrate as old
    from storage.migrations.core.v072_moderator_dashboard import migrate as new
    async with asqlite.create_pool(str(tmp_path/'upgrade.db')) as db:
        async with db.acquire() as conn:
            await old(conn)
            await conn.execute("INSERT INTO channel_access VALUES ('1','2','Streamer','Viewer','notes','view')")
            await conn.execute("INSERT INTO channel_access VALUES ('1','3','Streamer','Editor','notes','edit')")
            await new(conn)
            rows=await conn.fetchall('SELECT feature, permission FROM channel_access ORDER BY user_id')
            assert [tuple(row) for row in rows]==[('dashboard','view'),('dashboard','edit')]


@pytest.mark.asyncio
async def test_owner_overview_keeps_owner_urls_and_shortcuts(env):
    client,session,db,bot=env
    session['channel_user_id']='1'
    page=await client.get('/channel')
    assert page.status_code==200
    assert 'data-stream-url="/channel/api/chat/stream?view=both"' in page.text
    assert 'data-raid-browser-open' in page.text
    assert 'contenteditable="plaintext-only"' in page.text
    assert 'data-for-you data-csrf-token' in page.text
    assert 'Moderator dashboard' not in page.text
    assert 'data-youtube-connected="true"' in page.text


@pytest.mark.asyncio
async def test_navigation_authorization_and_reauthorization_requirements(env, monkeypatch):
    client, session, db, bot = env
    await set_grant(db, '1', '2', 'Streamer', 'Alice', 'view')
    await set_grant(db, '3', '2', 'Other channel', 'Alice', 'edit')
    page = (await client.get('/me/mod/1')).text
    nav = page.split('<nav class="navigation moderator-navigation">')[1].split('</nav>')[0]
    import re
    assert re.findall(r'<span class="nav-link-label">(.*?)</span>', nav) == ['My account', 'Overview', 'Other channel', 'Streamer']
    assert nav.count('<svg') == 4
    assert '<hr ' in nav
    assert '/connect' not in nav and '/notes' not in nav
    assert 'data-mod-auth-banner>' in page
    token = TwitchTokenResponse('access', 'refresh', 3600, list(twitch_actions.CHAT_SCOPES), 'bearer')
    await twitch_actions.save_credentials(db, '2', token)
    assert (await client.get('/me/mod/1/api/authorization')).json() == {'required': False}
    page = (await client.get('/me/mod/1')).text
    assert 'data-mod-auth-banner hidden>' in page
    await set_grant(db, '1', '2', 'Streamer', 'Alice', 'edit')
    assert (await client.get('/me/mod/1/api/authorization')).json()['required']
    token = TwitchTokenResponse('access', 'refresh', 3600, list(twitch_actions.MOD_SCOPES), 'bearer')
    await twitch_actions.save_credentials(db, '2', token)
    assert not (await client.get('/me/mod/1/api/authorization')).json()['required']
    monkeypatch.setattr(twitch_actions, 'AUTHORIZATION_REVISION', 2)
    assert (await client.get('/me/mod/1/api/authorization')).json()['required']
    await twitch_actions.save_credentials(db, '2', token)
    assert not (await client.get('/me/mod/1/api/authorization')).json()['required']
    await twitch_actions.invalidate_credentials(db, '2')
    assert (await client.get('/me/mod/1/api/authorization')).json()['required']
    await set_grant(db, '3', '2', '', '', 'revoke')
    page = (await client.get('/me/mod/1')).text
    assert 'href="/me/mod/3"' not in page


@pytest.mark.asyncio
async def test_ads_are_super_only_and_audience_metrics_stay_private(env, monkeypatch):
    client, session, db, bot = env
    stats = [{'key': key, 'label': key, 'display_value': '42'} for key in ('viewers','followers','subscribers','points_lost')]
    monkeypatch.setattr(owner, 'get_dashboard_header_stats', AsyncMock(return_value=stats))
    for role in ('view', 'edit', 'super'):
        await set_grant(db, '1', '2', 'Streamer', 'Alice', role)
        page = (await client.get('/me/mod/1')).text
        assert 'data-dashboard-stat=' not in page
        assert 'data-dashboard-points-lost>' in page
        assert 'class="mod-predictions' not in page
        assert ('data-ad-panel ' in page) == (role == 'super')
        response = await client.get('/me/mod/1/api/dashboard-stats')
        assert [s['key'] for s in response.json()['stats']] == ['points_lost']
        if role != 'super':
            assert (await client.get('/me/mod/1/api/ad-status')).status_code == 403
            assert (await client.post('/me/mod/1/api/ads/action', data={'csrf_token':'secret', 'action':'run-90'})).status_code == 403
        else:
            assert (await client.get('/me/mod/1/api/ad-status')).status_code == 200
            assert 'data-ad-action="run-90"' in page
            user = SimpleNamespace(start_commercial=AsyncMock(return_value=SimpleNamespace(message='', length=90)))
            bot.create_partialuser.return_value = user
            assert (await client.post('/me/mod/1/api/ads/action', data={'csrf_token':'secret', 'action':'run-90'})).status_code == 200
            user.start_commercial.assert_awaited_once_with(length=90)
    session['channel_user_id'] = '1'
    assert len((await client.get('/channel/api/dashboard-stats')).json()['stats']) == 4


@pytest.mark.asyncio
async def test_note_popup_creates_channel_note_once_and_enforces_permissions(env):
    from storage.for_you import notes_page
    client, session, db, bot = env
    data = {'csrf_token':'secret', 'submission_id':'a'*32, 'title':'Next stream', 'notes':'Remember the community game.', 'broadcaster_id':'99', 'actor':'99'}
    await set_grant(db,'1','2','Streamer','Alice','view')
    assert (await client.post('/me/mod/1/api/notes',data=data)).status_code == 403
    for role in ('edit','super'):
        await set_grant(db,'1','2','Streamer','Alice',role)
        page=(await client.get('/me/mod/1')).text
        for label in ('Polls','Predictions','Shouts'):
            assert f'disabled title="{label} — coming soon"' in page
        assert 'data-mod-note-dialog' in page and 'data-mod-note-form' in page
        assert 'href="/me/mod/1/notes"' not in page
        assert (await client.post('/me/mod/1/api/notes',data={**data,'csrf_token':'bad'})).status_code == 403
        assert (await client.post('/me/mod/1/api/notes',data={**data,'notes':'   '})).status_code == 400
        assert (await client.post('/me/mod/1/api/notes',data={**data,'submission_id':'bad'})).status_code == 422
        saved=await client.post('/me/mod/1/api/notes',data=data)
        assert saved.status_code == 200
        assert saved.json()['note']['notes'] == data['notes']
    owner_notes=await notes_page(db,'1')
    assert len(owner_notes['items']) == 1
    assert owner_notes['items'][0]['title'] == 'Next stream'
    assert not (await notes_page(db,'99'))['items']
    async with db.acquire() as connection:
        logs=await connection.fetchall("SELECT * FROM channel_access_audit WHERE action='notes:create'")
        assert len(logs)==1 and logs[0]['actor_id']=='2' and logs[0]['broadcaster_id']=='1'
    await set_grant(db,'1','2','','','revoke')
    assert (await client.post('/me/mod/1/api/notes',data=data)).status_code == 403
