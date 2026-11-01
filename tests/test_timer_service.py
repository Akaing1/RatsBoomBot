from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from bot.timer_messages import TimerMessage, format_timers, parse_timers
from bot.services.stream.timers import TimerService
from bot.services.channels.profile_settings import ProfileSettingsService


async def make_service(monkeypatch, timers):
    profile = SimpleNamespace(timer_messages=timers)
    identity = SimpleNamespace(send_announcement=AsyncMock(), send_message=AsyncMock())
    bot = SimpleNamespace(create_partialuser=lambda channel: channel, services=SimpleNamespace(
        chat_identity=identity, stream_logs=SimpleNamespace(write=MagicMock()), features=SimpleNamespace(is_enabled=lambda *args: True)))
    settings = SimpleNamespace(timers_enabled=True, discord_url=None, youtube_url=None)
    service = TimerService(bot, SimpleNamespace(get_live_broadcasters=AsyncMock(return_value={'1': 'Mei'})), SimpleNamespace(get_settings=AsyncMock(return_value=settings)))
    monkeypatch.setattr('bot.services.stream.timers.get_active_profile', lambda _: profile)
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 0)
    await service.check_announcements()
    return service, identity, profile


@pytest.mark.asyncio
@pytest.mark.parametrize('require_chat,minimum,elapsed,messages,sent', [
    (True, 20, 599, 20, False), (True, 20, 600, 20, True),
    (True, 20, 600, 19, False), (True, 50, 600, 49, False),
    (True, 50, 600, 50, True), (False, 20, 599, 0, False),
    (False, 20, 600, 0, True),
])
async def test_configured_schedule_and_activity_gate(monkeypatch, require_chat, minimum, elapsed, messages, sent):
    timer = TimerMessage('Custom timer', interval_minutes=10, require_active_chat=require_chat, minimum_messages=minimum)
    service, identity, _ = await make_service(monkeypatch, (timer,))
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: elapsed)
    service.message_counts['1'] = messages
    await service.check_announcements()
    assert identity.send_message.await_count == int(sent)


@pytest.mark.asyncio
async def test_each_timer_has_independent_interval_and_message_baseline(monkeypatch):
    timers = (TimerMessage('Quiet chat', interval_minutes=5, require_active_chat=False),
              TimerMessage('Active chat', interval_minutes=10, minimum_messages=3))
    service, identity, _ = await make_service(monkeypatch, timers)
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 300)
    service.message_counts['1'] = 2
    await service.check_announcements()
    assert identity.send_message.await_args_list == [call('1', 'Quiet chat')]
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 600)
    service.message_counts['1'] = 3
    await service.check_announcements()
    assert identity.send_message.await_args_list[-2:] == [call('1', 'Quiet chat'), call('1', 'Active chat')]
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 1200)
    service.message_counts['1'] = 5
    await service.check_announcements()
    assert identity.send_message.await_args == call('1', 'Quiet chat')
    service.message_counts['1'] = 6
    await service.check_announcements()
    assert identity.send_message.await_args == call('1', 'Active chat')


@pytest.mark.asyncio
async def test_announcement_fallback_advances_only_that_timer(monkeypatch):
    timer = TimerMessage('Promo', 'announcement', 'orange', interval_minutes=1, require_active_chat=False)
    service, identity, _ = await make_service(monkeypatch, (timer,))
    identity.send_announcement.side_effect = RuntimeError('Twitch failed')
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 60)
    await service.check_announcements()
    identity.send_message.assert_awaited_once_with('1', 'Promo')
    await service.check_announcements()
    assert identity.send_message.await_count == 1


@pytest.mark.asyncio
async def test_failed_delivery_can_retry_without_blocking_other_timers(monkeypatch):
    timers = (TimerMessage('Failing', interval_minutes=1, require_active_chat=False),
              TimerMessage('Healthy', interval_minutes=1, require_active_chat=False))
    service, identity, _ = await make_service(monkeypatch, timers)
    identity.send_message.side_effect = [RuntimeError('Chat failed'), None]
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 60)
    await service.check_announcements()
    assert identity.send_message.await_args_list == [call('1', 'Failing'), call('1', 'Healthy')]
    identity.send_message.side_effect = None
    await service.check_announcements()
    assert identity.send_message.await_args_list[-1] == call('1', 'Failing')
    assert identity.send_message.await_count == 3


@pytest.mark.asyncio
async def test_reordering_preserves_timer_progress_and_removed_timers_are_pruned(monkeypatch):
    timers = (TimerMessage('First', interval_minutes=1, require_active_chat=False),
              TimerMessage('Second', interval_minutes=2, require_active_chat=False))
    service, identity, profile = await make_service(monkeypatch, timers)
    profile.timer_messages = timers[::-1]
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 60)
    await service.check_announcements()
    identity.send_message.assert_awaited_once_with('1', 'First')
    profile.timer_messages = (timers[1],)
    monkeypatch.setattr('bot.services.stream.timers.time.time', lambda: 120)
    await service.check_announcements()
    assert identity.send_message.await_args == call('1', 'Second')
    assert len(service.timer_progress['1']) == 1


@pytest.mark.parametrize('options', [
    {'interval_minutes': 0}, {'interval_minutes': 1441}, {'interval_minutes': True},
    {'minimum_messages': 0}, {'minimum_messages': 100001}, {'require_active_chat': 'false'},
])
def test_invalid_timer_schedules_are_rejected(options):
    with pytest.raises(ValueError):
        TimerMessage('Test', **options)


def test_timer_editor_round_trip_and_legacy_text():
    entries = (TimerMessage('Promo', 'announcement', 'orange', interval_minutes=5, require_active_chat=False),
               TimerMessage('Social', interval_minutes=15, minimum_messages=40))
    definition = ProfileSettingsService.get_definition('timer_messages')
    saved = ProfileSettingsService.validate_value(definition, format_timers(entries))
    assert parse_timers(saved) == entries
    assert parse_timers('First\nSecond') == (TimerMessage('First'), TimerMessage('Second'))
    assert parse_timers('[["Legacy", "announcement", "blue", true]]')[0].interval_minutes == 30
    with pytest.raises(ValueError):
        ProfileSettingsService.validate_value(definition, '[["Promo", "message", "primary", true, 0, true, 20]]')


def test_disabled_timers_are_excluded_and_placeholder_rendering_preserves_schedule():
    timer = TimerMessage('On {discord_url}', 'announcement', 'green', interval_minutes=7, minimum_messages=6)
    entries = (TimerMessage('Off', enabled=False), timer)
    settings = SimpleNamespace(discord_url='discord.test', youtube_url=None)
    messages = TimerService.get_messages(entries, settings)
    assert len(messages) == 1
    assert messages[0].message == 'On discord.test'
    assert (messages[0].interval_minutes, messages[0].minimum_messages) == (7, 6)
    assert TimerService.get_messages((entries[0],), settings) == []
    assert parse_timers(format_timers(entries)) == entries
