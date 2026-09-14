from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.timer_messages import TimerMessage, format_timers, parse_timers
from bot.services.stream.timers import TimerService
from bot.services.channels.profile_settings import ProfileSettingsService


def make_service(monkeypatch):
    profile = SimpleNamespace(timer_messages=(("Promo", "announcement", "orange"), ("Social", "message")))
    identity = SimpleNamespace(send_announcement=AsyncMock(), send_message=AsyncMock())
    bot = SimpleNamespace(create_partialuser=lambda channel: channel, services=SimpleNamespace(
        chat_identity=identity, stream_logs=SimpleNamespace(write=MagicMock()), features=SimpleNamespace(is_enabled=lambda *args: True)))
    settings = SimpleNamespace(timers_enabled=True, discord_url=None, youtube_url=None)
    service = TimerService(bot, SimpleNamespace(get_live_broadcasters=AsyncMock(return_value={"1": "Mei"})), SimpleNamespace(get_settings=AsyncMock(return_value=settings)))
    monkeypatch.setattr("bot.services.stream.timers.get_active_profile", lambda _: profile)
    service.last_announcements["1"] = 0
    service.message_counts["1"] = 20
    return service, identity


@pytest.mark.asyncio
async def test_mixed_rotation_shares_interval_and_message_gate(monkeypatch):
    service, identity = make_service(monkeypatch)
    monkeypatch.setattr("bot.services.stream.timers.time.time", lambda: 1800)
    await service.check_announcements()
    identity.send_announcement.assert_awaited_once_with("1", "Promo", "orange")
    identity.send_message.assert_not_awaited()
    service.message_counts["1"] = 20
    await service.check_announcements()
    identity.send_message.assert_not_awaited()
    monkeypatch.setattr("bot.services.stream.timers.time.time", lambda: 3600)
    service.message_counts["1"] = 19
    await service.check_announcements()
    identity.send_message.assert_not_awaited()
    service.message_counts["1"] = 20
    await service.check_announcements()
    identity.send_message.assert_awaited_once_with("1", "Social")


@pytest.mark.asyncio
async def test_announcement_fallback_consumes_one_slot(monkeypatch):
    service, identity = make_service(monkeypatch)
    identity.send_announcement.side_effect = RuntimeError("Twitch failed")
    monkeypatch.setattr("bot.services.stream.timers.time.time", lambda: 1800)
    await service.check_announcements()
    identity.send_message.assert_awaited_once_with("1", "Promo")
    assert service.message_indexes["1"] == 1
    assert service.message_counts["1"] == 0


@pytest.mark.asyncio
async def test_failed_delivery_keeps_rotation_slot(monkeypatch):
    service, identity = make_service(monkeypatch)
    identity.send_announcement.side_effect = RuntimeError("Twitch failed")
    identity.send_message.side_effect = RuntimeError("Chat failed")
    monkeypatch.setattr("bot.services.stream.timers.time.time", lambda: 1800)
    await service.check_announcements()
    assert service.message_indexes.get("1", 0) == 0
    assert service.last_announcements["1"] == 0
    assert service.message_counts["1"] == 20


def test_timer_editor_round_trip_and_legacy_text():
    entries = (TimerMessage("Promo", "announcement", "orange"), TimerMessage("Social"))
    definition = ProfileSettingsService.get_definition("timer_messages")
    saved = ProfileSettingsService.validate_value(definition, format_timers(entries))
    assert parse_timers(saved) == entries
    assert parse_timers("First\nSecond") == (TimerMessage("First"), TimerMessage("Second"))
    with pytest.raises(ValueError):
        ProfileSettingsService.validate_value(definition, '[["Promo", "invalid"]]')
