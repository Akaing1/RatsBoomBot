import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from bot.chat_preferences import normalize_chat_preferences
from bot.services.channels.live_chat import LiveChatService
from storage.migration_runner import run_migrations
from web.channel.auth import CHANNEL_USER_ID_KEY
from web.channel.routers import dashboard
from web.public import routers as public
from web.shared.live_chat import stream_chat_events

PREFERENCES = {'version': 8, 'origin': 'all', 'channels': {}, 'connectedPlatforms': ['twitch', 'youtube'],
               'users': ['mods', 'youtube_members'], 'types': ['messages']}


@pytest.mark.parametrize('value', [None, [], {}, {**PREFERENCES, 'users': ['bad-role']},
    {**PREFERENCES, 'types': 'messages'}, {**PREFERENCES, 'secret': 'oops'},
    {**PREFERENCES, 'connectedPlatforms': ['discord']}])
def test_invalid_preferences_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_chat_preferences(value)


def test_gif_preferences_migrate_old_message_filters_without_overriding_new_selections():
    old = {**PREFERENCES, 'version': 6}
    assert normalize_chat_preferences(old)['types'] == ['messages', 'gifs', 'bits']
    assert normalize_chat_preferences({**old, 'types': ['commands']})['types'] == ['commands']
    assert normalize_chat_preferences(PREFERENCES)['types'] == ['messages']
    assert normalize_chat_preferences({**PREFERENCES, 'types': ['gifs']})['types'] == ['gifs']


def test_event_type_filters_migrate_previous_categories_and_keep_current_selections():
    previous = {**PREFERENCES, 'version': 7, 'types': ['messages', 'redeems']}
    assert normalize_chat_preferences(previous)['types'] == ['messages', 'redeems', 'bits', 'watch_streaks']
    for event in ['bits', 'watch_streaks']:
        assert normalize_chat_preferences({**PREFERENCES, 'types': [event]})['types'] == [event]


@pytest.mark.asyncio
async def test_preferences_persist_notify_only_the_channel_and_replay_before_history(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'chat.db')) as db:
        await run_migrations(db)
        live = LiveChatService(db)
        await live.setup()
        other_queue = live.subscribe('other')
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        events = stream_chat_events(request, live, 'owner', 'both', mirror_preferences=True)
        assert await anext(events) == 'retry: 2000\n\n'
        assert 'data: null' in await anext(events)
        assert 'history-complete' in await anext(events)
        pending = asyncio.create_task(anext(events))
        await asyncio.sleep(0)
        await live.set_chat_preferences('owner', PREFERENCES)
        assert json.dumps(PREFERENCES) in await asyncio.wait_for(pending, 1)
        assert other_queue.empty()
        assert live.get_chat_preferences('other') is None
        await events.aclose()
        assert 'owner' not in live.subscribers
        restarted = LiveChatService(db)
        await restarted.setup()
        assert restarted.get_chat_preferences('owner') == PREFERENCES
        events = stream_chat_events(request, restarted, 'owner', 'both', mirror_preferences=True)
        await anext(events)
        assert json.dumps(PREFERENCES) in await anext(events)
        await events.aclose()


def request(owner='owner'):
    return Request({'type': 'http', 'path': '/', 'headers': [], 'session': {
        **({CHANNEL_USER_ID_KEY: owner} if owner else {}), 'csrf_token': 'valid'}})


@pytest.mark.asyncio
async def test_owner_api_enforces_auth_csrf_validation_and_channel_scope(monkeypatch):
    live = SimpleNamespace(set_chat_preferences=AsyncMock(return_value=PREFERENCES),
                           get_chat_preferences=lambda channel: None)
    bot = SimpleNamespace(services=SimpleNamespace(live_chat=live,
        broadcasters=SimpleNamespace(get_broadcasters=lambda: {'owner': SimpleNamespace(id='owner')})))
    monkeypatch.setattr(dashboard, 'get_bot', lambda: bot)
    assert (await dashboard.channel_chat_preferences(request(None))).status_code == 401
    with pytest.raises(HTTPException) as error:
        await dashboard.update_channel_chat_preferences(request(), json.dumps(PREFERENCES), 'bad')
    assert error.value.status_code == 403
    assert (await dashboard.update_channel_chat_preferences(request(), '{bad', 'valid')).status_code == 400
    assert (await dashboard.update_channel_chat_preferences(request(), json.dumps(PREFERENCES), 'valid')).status_code == 200
    live.set_chat_preferences.assert_awaited_once_with('owner', PREFERENCES)
    assert (await dashboard.channel_chat_preferences(request())).headers['cache-control'] == 'no-store'


@pytest.mark.asyncio
async def test_legacy_widget_parameters_use_the_mirrored_feed_and_rotation_revokes_open_stream(monkeypatch):
    live = LiveChatService(None)
    live.token_broadcasters['valid'] = 'owner'
    bot = SimpleNamespace(services=SimpleNamespace(live_chat=live))
    monkeypatch.setattr(public, 'get_bot', lambda: bot)
    assert (await public.chat_widget_events(request(), 'bad')).status_code == 404
    req = request()
    req.is_disconnected = AsyncMock(return_value=False)
    response = await public.chat_widget_events(req, 'valid', 'commands')
    events = response.body_iterator
    assert await anext(events) == 'retry: 2000\n\n'
    assert 'chat-preferences' in await anext(events)
    assert 'history-complete' in await anext(events)
    live.token_broadcasters.pop('valid')
    assert 'access-revoked' in await anext(events)
    await events.aclose()
    assert not live.subscribers

@pytest.mark.asyncio
async def test_dock_send_requires_owner_session_valid_token_and_csrf(monkeypatch):
    from web.channel.routers import dashboard
    live = SimpleNamespace(resolve_widget_token=lambda token: 'owner' if token == 'valid' else None)
    monkeypatch.setattr(public, 'get_bot', lambda: SimpleNamespace(services=SimpleNamespace(live_chat=live)))
    with pytest.raises(HTTPException):
        await public.chat_widget_send(request(), 'valid', 'hello', 'twitch', 'bad')
    send = AsyncMock(return_value=JSONResponse({'sent': ['twitch'], 'errors': {}}))
    monkeypatch.setattr(dashboard, 'channel_send_chat_message', send)
    assert (await public.chat_widget_send(request(None), 'valid', 'hello', 'twitch', 'valid')).status_code == 401
    assert (await public.chat_widget_send(request('other'), 'valid', 'hello', 'twitch', 'valid')).status_code == 401
    assert (await public.chat_widget_send(request(), 'revoked', 'hello', 'twitch', 'valid')).status_code == 404
    send.assert_not_awaited()
    req = request()
    assert (await public.chat_widget_send(req, 'valid', 'hello', 'twitch', 'valid')).status_code == 200
    send.assert_awaited_once_with(req, 'hello', 'twitch', 'valid', '')
