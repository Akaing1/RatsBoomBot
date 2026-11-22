import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers import dashboard
from bot.services.channels.stream_together import StreamTogetherService, StreamTogetherError
from web.admin.auth import CSRF_SESSION_KEY
from starlette.datastructures import FormData
from fastapi import HTTPException as FastAPIHTTPException
from twitchio import HTTPException


def guest_service(active=True, ready=True):
    session = {'id': 'call', 'guests': [{'slot_id': '0', 'user_id': '1'}, {'slot_id': '1', 'user_id': '2'}]}
    async def respond(route):
        if route.method != 'GET':
            return None
        if route.path.endswith('/session'):
            return {'data': [session] if active else []}
        if route.path.endswith('/channel_settings'):
            return {'data': [{'slot_count': 6, 'browser_source_token': 'secret'}]}
        return {'data': [{'user_id': '3', 'status': 'READY' if ready else 'INVITED'}]}
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock(side_effect=respond)))
    return StreamTogetherService(bot), bot._http.request_json


@pytest.mark.asyncio
async def test_guest_state_reuses_cache_and_never_exposes_browser_source_token():
    import asyncio
    service, http = guest_service()
    first, second = await asyncio.gather(service.state('1'), service.state('1'))
    assert first == second
    assert first['slot_count'] == 6
    assert 'secret' not in json.dumps(first)
    assert http.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('guest_slot_zero', [False, True])
async def test_connected_session_uses_guest_token_host_id_and_verifies_membership(guest_slot_zero):
    service, http = guest_service()
    if guest_slot_zero:
        http.return_value = {'data': [{'id': 'call', 'guests': [{'slot_id': '0', 'user_id': '2'}, {'slot_id': '1', 'user_id': '1'}]}]}
        http.side_effect = None
    result = await service.connected_state('2', '1')
    assert result['is_host'] is False
    assert result['invites'] == []
    route = http.await_args.args[0]
    assert route.token_for == '2'
    assert route.params == {'broadcaster_id': '1', 'moderator_id': '2'}
    assert await service.connected_state('2', '1') == result
    assert http.await_count == 1
    assert await service.connected_state('3', '1') is None
    assert await service.connected_state('2', 'bad') is None
    assert await service.connected_state('2', '2') is None


@pytest.mark.asyncio
@pytest.mark.parametrize('action,values,method,path,expected', [
    ('start', {}, 'POST', 'session', {}),
    ('end', {}, 'DELETE', 'session', {}),
    ('invite', {'guest_id': '3'}, 'POST', 'invites', {'guest_id': '3'}),
    ('revoke', {'guest_id': '3'}, 'DELETE', 'invites', {'guest_id': '3'}),
    ('assign', {'guest_id': '3', 'slot_id': '2'}, 'POST', 'slot', {'guest_id': '3', 'slot_id': '2'}),
    ('move', {'slot_id': '1', 'destination_slot_id': '2'}, 'PATCH', 'slot', {'source_slot_id': '1', 'destination_slot_id': '2'}),
    ('remove', {'guest_id': '2', 'slot_id': '1'}, 'DELETE', 'slot', {'guest_id': '2', 'slot_id': '1'}),
    ('settings', {'slot_id': '1', 'is_audio_enabled': 'false', 'is_video_enabled': 'true', 'is_live': 'false', 'volume': '35'}, 'PATCH', 'slot_settings',
     {'slot_id': '1', 'is_audio_enabled': 'false', 'is_video_enabled': 'true', 'is_live': 'false', 'volume': '35'}),
])
async def test_guest_actions_use_owner_token_and_documented_query_parameters(action, values, method, path, expected):
    service, http = guest_service(active=action != 'start')
    await service.action('1', action, {'session_id': 'call', 'broadcaster_id': 'attacker', **values})
    route = http.await_args.args[0]
    assert (route.method, route.path, route.token_for) == (method, f'guest_star/{path}', '1')
    params = {'broadcaster_id': '1', **expected}
    if action != 'start': params['session_id'] = 'call'
    if path != 'session': params['moderator_id'] = '1'
    assert route.params == params
    assert '1' not in service._states


@pytest.mark.asyncio
@pytest.mark.parametrize('action,values', [
    ('end', {'session_id': 'old'}), ('start', {}), ('invite', {'guest_id': '1'}),
    ('assign', {'guest_id': '4', 'slot_id': '2'}), ('assign', {'guest_id': '3', 'slot_id': '0'}),
    ('move', {'slot_id': '1', 'destination_slot_id': '7'}), ('move', {'slot_id': '4', 'destination_slot_id': '2'}),
    ('remove', {'guest_id': '3', 'slot_id': '1'}), ('settings', {'slot_id': '0', 'is_live': 'false'}),
    ('settings', {'slot_id': '1', 'volume': '101'}), ('settings', {'slot_id': '1', 'is_live': 'yes'}),
    ('settings', {'slot_id': '1'}), ('unknown', {}),
])
async def test_guest_actions_reject_stale_or_invalid_changes_without_writing(action, values):
    service, http = guest_service()
    with pytest.raises(StreamTogetherError):
        await service.action('1', action, {'session_id': 'call', **values})
    assert all(call.args[0].method == 'GET' for call in http.await_args_list)


@pytest.mark.asyncio
async def test_guest_assign_waits_for_ready_and_write_failures_are_not_retried():
    service, http = guest_service(ready=False)
    with pytest.raises(StreamTogetherError, match='not ready'):
        await service.action('1', 'assign', {'session_id': 'call', 'guest_id': '3', 'slot_id': '2'})
    await service.state('1')
    http.side_effect = [ {'data': [{'id': 'call', 'guests': []}]}, {'data': []}, TimeoutError() ]
    with pytest.raises(TimeoutError):
        await service.action('1', 'invite', {'session_id': 'call', 'guest_id': '3'})
    writes = [call for call in http.await_args_list if call.args[0].method != 'GET']
    assert len(writes) == 1
    assert '1' not in service._states


def control_context(monkeypatch, delegated=False, csrf='csrf'):
    controls = SimpleNamespace(state=AsyncMock(return_value={'state': 'idle', 'session': None, 'slot_count': 6, 'invites': []}), action=AsyncMock())
    runtime = SimpleNamespace(services=SimpleNamespace(live_chat=SimpleNamespace(stream_together=controls),
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {'1': SimpleNamespace(id='1')})))
    monkeypatch.setattr(dashboard, 'get_bot', lambda: runtime)
    request = Request({'type': 'http', 'session': {CHANNEL_USER_ID_KEY: '1', CSRF_SESSION_KEY: csrf}})
    request._form = FormData({'session_id': 'call', 'guest_id': '2'})
    if delegated: request.state.channel_access = {'broadcaster_id': '1', 'user_id': '2'}
    return request, controls


@pytest.mark.asyncio
async def test_controls_require_owner_and_csrf(monkeypatch):
    request, controls = control_context(monkeypatch, delegated=True)
    assert (await dashboard.channel_stream_together_guests(request)).status_code == 403
    assert (await dashboard.channel_stream_together_control(request, 'end', 'csrf')).status_code == 403
    controls.action.assert_not_awaited(); controls.state.assert_not_awaited()
    request, controls = control_context(monkeypatch)
    with pytest.raises(FastAPIHTTPException):
        await dashboard.channel_stream_together_control(request, 'end', 'wrong')
    controls.action.assert_not_awaited()
    assert (await dashboard.channel_stream_together_control(request, 'end', 'csrf')).status_code == 200
    controls.action.assert_awaited_once_with('1', 'end', {'session_id': 'call', 'guest_id': '2'})


@pytest.mark.asyncio
async def test_controls_explain_missing_permission_and_preserve_shared_chat(monkeypatch):
    request, controls = control_context(monkeypatch)
    controls.state.side_effect = HTTPException(status=403, extra='forbidden', route=None)
    response = await dashboard.channel_stream_together_guests(request)
    assert response.status_code == 403
    assert json.loads(response.body)['reconnect'] is True


@pytest.mark.asyncio
async def test_guest_cards_include_stream_status_and_daily_profiles_without_mutating_session_cache(monkeypatch):
    request, controls = control_context(monkeypatch)
    session = {'id': 'call', 'guests': [{'user_id': '1', 'slot_id': '0'}, {'user_id': '2', 'slot_id': '1'}]}
    controls.state.return_value = {'session': session, 'invites': [], 'slot_count': 6}
    profiles = AsyncMock(return_value={'1': {'login': 'owner'}, '2': {'login': 'friend', 'profile_image_url': 'https://images.test/friend.png'}})
    streams = AsyncMock(return_value={'data': [{'user_id': '2', 'thumbnail_url': 'https://images.test/{width}x{height}.jpg'}]})
    monkeypatch.setattr(dashboard, 'raid_browser_profiles', profiles)
    monkeypatch.setattr(dashboard, 'raid_browser_cached_request', streams)
    response = await dashboard.channel_stream_together_guests(request)
    guests = json.loads(response.body)['session']['guests']
    assert guests[0]['is_streaming'] is False
    assert guests[1]['is_streaming'] is True
    assert guests[1]['user_login'] == 'friend'
    assert guests[1]['thumbnail_url'].startswith('https://images.test/640x360.jpg?t=')
    assert 'is_streaming' not in session['guests'][1]
    assert streams.await_args.args[2:] == ('streams', {'user_id': ['1', '2'], 'first': 100})


@pytest.mark.asyncio
@pytest.mark.parametrize('owner_forbidden', [False, True])
async def test_invited_guest_opens_the_connected_hosts_call(monkeypatch, owner_forbidden):
    request, controls = control_context(monkeypatch)
    live = dashboard.get_bot().services.live_chat
    live.shared_chat_participants = AsyncMock(return_value=[{'id': '2', 'name': 'Host'}])
    live.shared_chat_hosts = {'1': '2'}
    controls.connected_state = AsyncMock(return_value={'session': {'id': 'other-call', 'guests': [
        {'user_id': '2', 'slot_id': '1', 'user_login': 'host_channel'}, {'user_id': '1', 'slot_id': '0'}]},
        'invites': [], 'slot_count': 0, 'is_host': False})
    if owner_forbidden:
        controls.state.side_effect = HTTPException(status=403, extra='forbidden', route=None)
    monkeypatch.setattr(dashboard, 'raid_browser_profiles', AsyncMock(return_value={}))
    monkeypatch.setattr(dashboard, 'raid_browser_cached_request', AsyncMock(return_value={'data': []}))
    response = await dashboard.channel_stream_together_guests(request, refresh=True)
    live.shared_chat_participants.assert_awaited_once_with('1', refresh=True)
    assert response.status_code == 200
    data = json.loads(response.body)
    assert data['is_host'] is False
    assert data['call_url'] == 'https://www.twitch.tv/popout/host_channel/guest-star'
    controls.connected_state.assert_awaited_once_with('1', '2')


@pytest.mark.asyncio
async def test_named_host_can_show_guest_call_without_shared_chat(monkeypatch):
    request, controls = control_context(monkeypatch)
    controls.connected_state = AsyncMock(return_value={
        'session': {'id': 'other-call', 'guests': [{'user_id': '1', 'slot_id': '0'}, {'user_id': '2', 'slot_id': '1'}]},
        'invites': [], 'slot_count': 0, 'is_host': False,
    })
    monkeypatch.setattr(dashboard, 'raid_browser_profiles', AsyncMock(return_value={}))

    async def twitch_data(_bot, _channel_id, path, _params):
        return {'data': [{'id': '2', 'login': 'host_channel'}] if path == 'users' else []}

    monkeypatch.setattr(dashboard, 'raid_browser_cached_request', AsyncMock(side_effect=twitch_data))
    response = await dashboard.channel_stream_together_guests(request, guest_host='host_channel')
    assert response.status_code == 200
    data = json.loads(response.body)
    assert data['host_id'] == '2' and not data['is_host'] and not data['shared_chat_active']
    assert data['call_url'] == 'https://www.twitch.tv/popout/host_channel/guest-star'
    controls.connected_state.assert_awaited_once_with('1', '2')


@pytest.mark.asyncio
@pytest.mark.parametrize('solo', [False, True])
async def test_shared_chat_shows_call_when_guest_star_is_unavailable(monkeypatch, solo):
    request, controls = control_context(monkeypatch)
    runtime = dashboard.get_bot()
    runtime.services.broadcasters.get_broadcasters = lambda: {'1': SimpleNamespace(id='1', login='owner')}
    live = runtime.services.live_chat
    live.shared_chat_participants = AsyncMock(return_value=[] if solo else [{'id': '2', 'name': 'Host'}])
    live.shared_chat_hosts = {'1': '1' if solo else '2'}
    live.shared_chat_active = {'1': True}
    controls.state.side_effect = TimeoutError()
    controls.connected_state = AsyncMock(side_effect=HTTPException(status=403, extra='forbidden', route=None))
    monkeypatch.setattr(dashboard, 'raid_browser_profiles', AsyncMock(return_value={'2': {'login': 'other_host'}}))
    monkeypatch.setattr(dashboard, 'raid_browser_cached_request', AsyncMock(return_value={'data': []}))
    response = await dashboard.channel_stream_together_guests(request)
    assert response.status_code == 200
    data = json.loads(response.body)
    assert data['shared_chat_only'] is True and data['is_host'] is False
    assert {guest['user_id'] for guest in data['session']['guests']} == ({'1'} if solo else {'1', '2'})
    login = 'owner' if solo else 'other_host'
    assert data['call_url'] == f'https://www.twitch.tv/popout/{login}/guest-star'


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['call', 'shared', 'idle', 'solo', 'solo-timeout'])
async def test_preview_participants_merge_rosters_and_use_cached_profiles(monkeypatch, source):
    request, controls = control_context(monkeypatch)
    runtime = dashboard.get_bot()
    runtime.services.broadcasters.get_broadcasters = lambda: {'1': SimpleNamespace(id='1', login='owner')}
    runtime.services.live_chat.shared_chat_participants = AsyncMock(return_value=[{'id': '2', 'name': 'Friend'}] if source == 'shared' else [])
    if source == 'shared':
        controls.state.side_effect = HTTPException(status=403, extra='forbidden', route=None)
    elif source.startswith('solo'):
        runtime.services.live_chat.shared_chat_active = {'1': True}
        controls.state.side_effect = TimeoutError() if source == 'solo-timeout' else HTTPException(status=403, extra='forbidden', route=None)
    elif source == 'call':
        controls.state.return_value = {'session': {'guests': [{'user_id': '1'}, {'user_id': '2'}, {'user_id': 'SCREENSHARE'}]}}
    profiles = AsyncMock(return_value={'1': {'login': 'owner', 'display_name': 'Owner', 'profile_image_url': 'https://images.test/1.png'},
                                       '2': {'login': 'friend', 'display_name': 'Friend', 'profile_image_url': 'https://images.test/2.png'}})
    monkeypatch.setattr(dashboard, 'raid_browser_profiles', profiles)
    monkeypatch.setattr(dashboard, 'raid_browser_cached_request', AsyncMock(return_value={'data': [{'user_id': '2'}]}))
    response = await dashboard.channel_stream_together_participants(request)
    assert response.status_code == 200
    data = json.loads(response.body)
    entries = data['participants']
    assert data['shared_chat_active'] is (source in {'shared', 'solo', 'solo-timeout'})
    assert data['is_host'] is (source == 'call')
    if source == 'idle':
        assert entries == []
        profiles.assert_not_awaited()
        assert data['active'] is False
    elif source.startswith('solo'):
        assert [entry['login'] for entry in entries] == ['owner']
        assert data['active'] is True
        profiles.assert_awaited_once_with(runtime, '1', [{'id': '1'}])
    else:
        assert [entry['login'] for entry in entries] == ['owner', 'friend']
        assert entries[1]['profile_image_url'] == 'https://images.test/2.png'
        assert [entry['is_streaming'] for entry in entries] == [False, True]
        profiles.assert_awaited_once_with(runtime, '1', [{'id': '1'}, {'id': '2'}])
