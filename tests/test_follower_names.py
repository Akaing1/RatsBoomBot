import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot.shared.follower_names import ensure_follower_names, remember_follower, follower_names_state
from bot.shared.events.community import CommunityEvents
from web.shared.protected_users import search_protected_users


@pytest.mark.asyncio
async def test_dashboard_preload_is_shared_paginated_and_retains_follow_events():
    release = asyncio.Event()
    async def twitch(route):
        if 'after' not in route.params:
            await release.wait()
            return {'data': [{'user_id': '1', 'user_login': 'first', 'user_name': 'First'}], 'pagination': {'cursor': 'next'}}
        return {'data': [{'user_id': '2', 'user_login': 'second', 'user_name': 'Second'}], 'pagination': {}}
    bot = SimpleNamespace(bot_id='99', _http=SimpleNamespace(request_json=AsyncMock(side_effect=twitch)))
    ensure_follower_names(bot, '10')
    task = follower_names_state(bot, '10')['task']
    ensure_follower_names(bot, '10')
    assert follower_names_state(bot, '10')['task'] is task
    remember_follower(bot, '10', SimpleNamespace(id='3', name='newviewer', display_name='New Viewer'))
    release.set()
    await task
    assert set(follower_names_state(bot, '10')['users']) == {'1', '2', '3'}
    ensure_follower_names(bot, '10')
    assert bot._http.request_json.await_count == 2
    assert all(call.args[0].token_for == '10' for call in bot._http.request_json.await_args_list)
    cached = await search_protected_users(bot, '10', '', cached_only=True)
    assert {user['id'] for user in cached} == {'1', '2', '3'}


@pytest.mark.asyncio
async def test_existing_follower_snapshot_is_reused_without_requests():
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock()), _followers_directory_cache={
        '10': {'refreshed': 1, 'loading': False, 'error': '', 'followers': [{'user_id': '1', 'user_login': 'viewer', 'user_name': 'Viewer'}]},
    })
    ensure_follower_names(bot, '10')
    assert follower_names_state(bot, '10')['loaded']
    bot._http.request_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_follow_events_update_names_even_when_response_messages_are_disabled():
    bot = SimpleNamespace(services=SimpleNamespace(features=SimpleNamespace(is_enabled=lambda *args: False), stream_logs=SimpleNamespace(write=Mock())))
    payload = SimpleNamespace(broadcaster=SimpleNamespace(id='10', name='owner'), user=SimpleNamespace(id='1', name='viewer', display_name='Viewer'))
    await CommunityEvents(bot).event_follow(payload)
    assert follower_names_state(bot, '10')['users']['1']['user_login'] == 'viewer'
    assert not follower_names_state(bot, '10')['loaded']


@pytest.mark.asyncio
async def test_preload_failure_does_not_break_dashboard_or_retry_immediately():
    bot = SimpleNamespace(_http=SimpleNamespace(request_json=AsyncMock(side_effect=RuntimeError('Unavailable'))))
    ensure_follower_names(bot, '10')
    task = follower_names_state(bot, '10')['task']
    await task
    ensure_follower_names(bot, '10')
    assert follower_names_state(bot, '10')['task'] is task
    assert not follower_names_state(bot, '10')['loaded']


@pytest.mark.asyncio
async def test_following_preload_is_shared_paginated_and_available_to_cache_only_search():
    from bot.shared.follower_names import ensure_following_names
    from web.channel.routers.dashboard import raid_browser_cached_request, ensure_user_search_names, user_search_names_loading
    release = asyncio.Event()
    async def twitch(route):
        if route.path == 'channels/followers':
            return {'data': [{'user_id': '1', 'user_login': 'follower', 'user_name': 'Follower'}]}
        await release.wait()
        if 'after' not in route.params:
            return {'data': [{'broadcaster_id': '2', 'broadcaster_login': 'following', 'broadcaster_name': 'Following'}], 'pagination': {'cursor': 'next'}}
        return {'data': [{'broadcaster_id': '3', 'broadcaster_login': 'other', 'broadcaster_name': 'Other'}]}
    bot = SimpleNamespace(bot_id='99', _http=SimpleNamespace(request_json=AsyncMock(side_effect=twitch)))
    ensure_user_search_names(bot, '10')
    task = bot._following_names_cache['10']['task']
    ensure_user_search_names(bot, '10')
    assert task is bot._following_names_cache['10']['task']
    assert user_search_names_loading(bot, '10')
    release.set()
    await asyncio.gather(task, follower_names_state(bot, '10')['task'])
    assert not user_search_names_loading(bot, '10')
    users = await search_protected_users(bot, '10', '', cached_only=True)
    assert {user['id'] for user in users} == {'1', '2', '3'}
    assert all(user['related'] for user in users)
    await raid_browser_cached_request(bot, '10', 'channels/followed', {'user_id': '10', 'first': 100})
    ensure_user_search_names(bot, '10')
    assert bot._http.request_json.await_count == 3
