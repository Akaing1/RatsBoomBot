from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from twitchio.ext import commands

from bot.services.channels.live_chat import LiveChatService
from bot.shared.events.chat import ChatEvents
from bot.shared_chat import is_shared_message
from bot.chat_preferences import normalize_chat_preferences


def payload(source='other'):
    return SimpleNamespace(id='destination-message', text='!points', badges=[],
        broadcaster=SimpleNamespace(id='owner', name='owner'),
        source_broadcaster=SimpleNamespace(id=source, name=source, display_name='Other Streamer') if source else None,
        source_id='original-message', source_badges=[SimpleNamespace(set_id='vip', id='1')],
        chatter=SimpleNamespace(id='viewer', name='viewer', display_name='Viewer', is_moderator=True), fragments=[])


def test_source_metadata_badges_and_destination_ids_survive_history():
    live = LiveChatService(None)
    msg = payload()
    result = live.publish_twitch(msg)
    assert result.is_shared
    assert result.source_channel_id == 'other'
    assert result.source_channel_name == 'Other Streamer'
    assert result.source_message_id == 'original-message'
    assert result.id == 'twitch:destination-message'
    assert result.accent == 'vip'
    assert [badge.name for badge in result.badges] == ['vip']
    live.publish_twitch(msg)
    assert len(live.history('owner')) == 1
    assert live.history('owner')[0]['is_shared'] is True
    assert live.history('other') == []
    msg.source_badges = []
    msg.id = 'no-source-badges'
    assert live.publish_twitch(msg).badges == ()


@pytest.mark.parametrize('source', [None, 'owner'])
def test_local_messages_are_not_classified_as_relayed(source):
    assert not is_shared_message(payload(source))


@pytest.mark.asyncio
async def test_relayed_message_is_display_only_and_never_reaches_channel_services():
    live = SimpleNamespace(publish_twitch=Mock())
    # Deliberately omit all reward/stat/moderation services: touching any is a failure.
    bot = SimpleNamespace(services=SimpleNamespace(live_chat=live))
    msg = payload()
    await ChatEvents(bot).event_message(msg)
    live.publish_twitch.assert_called_once_with(msg)


@pytest.mark.asyncio
async def test_twitchio_command_dispatch_ignores_relayed_commands_but_processes_local_ones():
    bot = SimpleNamespace(bot_id='bot', process_commands=AsyncMock())
    await commands.Bot.event_message(bot, payload())
    bot.process_commands.assert_not_awaited()
    local = payload(None)
    await commands.Bot.event_message(bot, local)
    bot.process_commands.assert_awaited_once_with(local)


@pytest.mark.asyncio
async def test_shared_notification_is_displayed_without_automatic_shoutouts():
    live = SimpleNamespace(publish_twitch_notification=Mock())
    bot = SimpleNamespace(services=SimpleNamespace(live_chat=live))
    msg = payload()
    msg.notice_type = 'watch_streak'
    await ChatEvents(bot).event_chat_notification(msg)
    live.publish_twitch_notification.assert_called_once_with(msg)


def test_old_preferences_enable_all_sources_and_invalid_source_is_rejected():
    old = {'version': 4, 'connectedPlatforms': ['twitch'], 'users': ['mods'], 'types': ['messages']}
    assert normalize_chat_preferences(old)['origin'] == 'all'
    assert normalize_chat_preferences({**old, 'origin': 'shared'})['origin'] == 'shared'
    with pytest.raises(ValueError):
        normalize_chat_preferences({**old, 'origin': 'unknown'})


def test_preview_preserves_shared_source_and_uses_source_roles():
    from web.shared.raid_chat import chat_event
    rendered = chat_event('channel.chat.message', {
        'broadcaster_user_id': 'owner', 'message_id': 'destination',
        'source_broadcaster_user_id': 'other', 'source_broadcaster_user_login': 'other',
        'source_broadcaster_user_name': 'Other Streamer', 'source_message_id': 'original',
        'badges': [{'set_id': 'moderator', 'id': '1'}],
        'source_badges': [{'set_id': 'vip', 'id': '1'}], 'message': {'text': 'hi'}})['message']
    assert rendered['is_shared']
    assert rendered['source_channel_name'] == 'Other Streamer'
    assert rendered['source_message_id'] == 'original'
    assert rendered['accent'] == 'vip'

@pytest.mark.parametrize('channels', [[], {'local': 1}, {'bad': True}, {'123': 'yes'}, {'١٢٣': True}])
def test_invalid_channel_preferences_are_rejected(channels):
    with pytest.raises(ValueError):
        normalize_chat_preferences({'connectedPlatforms': ['twitch'], 'users': [], 'types': [], 'channels': channels})


@pytest.mark.asyncio
async def test_roster_includes_quiet_participants_caches_names_and_clears_on_session_end(monkeypatch):
    import asyncio
    import httpx
    import bot.services.channels.live_chat as module
    clock = [100]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    live = LiveChatService(None, bot=SimpleNamespace(tokens={'1': {'token': 'test'}}))
    live.client = Mock()
    live._fetch_twitch_emote_page = AsyncMock(return_value={'data': [{'participants': [
        {'broadcaster_id': '1'}, {'broadcaster_id': '2'}, {'broadcaster_id': '3'}]}]})
    live._fetch_twitch_owner_names = AsyncMock(return_value={'2': 'Rat', '3': 'Friend'})
    expected = [{'id': '2', 'name': 'Rat'}, {'id': '3', 'name': 'Friend'}]
    results = await asyncio.gather(live.shared_chat_participants('1'), live.shared_chat_participants('1'))
    assert results == [expected, expected]
    assert live._fetch_twitch_emote_page.await_count == 1
    clock[0] += 31
    assert await live.shared_chat_participants('1') == expected
    assert live._fetch_twitch_owner_names.await_count == 1
    clock[0] += 31
    live._fetch_twitch_emote_page.side_effect = httpx.ConnectError('offline')
    assert await live.shared_chat_participants('1') == expected
    clock[0] += 31
    live._fetch_twitch_emote_page.side_effect = None
    live._fetch_twitch_emote_page.return_value = {'data': []}
    assert await live.shared_chat_participants('1') == []


@pytest.mark.asyncio
async def test_roster_is_sent_before_chat_history_and_changes_on_open_stream(monkeypatch):
    import web.shared.live_chat as module
    clock = [100]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])
    live = LiveChatService(None)
    live.shared_chat_participants = AsyncMock(side_effect=[[{'id': '2', 'name': 'Rat'}], []])
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    events = module.stream_chat_events(request, live, '1', 'both')
    assert 'retry:' in await anext(events)
    assert '"name": "Rat"' in await anext(events)
    assert 'history-complete' in await anext(events)
    clock[0] += 31
    assert 'chat-participants\ndata: []' in await anext(events)
    await events.aclose()
    assert '1' not in live.subscribers
