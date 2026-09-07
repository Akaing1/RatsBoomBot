from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.profiles import TimedAnnouncement
from bot.services.stream.timers import TimerService


@pytest.mark.asyncio
async def test_profile_timed_announcement_requires_interval_and_message_count(monkeypatch) -> None:
    announcement = TimedAnnouncement(message="Support Mei on YouTube!", interval_seconds=3600, required_messages=30, color="red")
    profile = SimpleNamespace(timed_announcements=(announcement,))
    chat_identity = SimpleNamespace(send_announcement=AsyncMock(), send_message=AsyncMock())
    bot = SimpleNamespace(create_partialuser=lambda broadcaster_id: SimpleNamespace(id=broadcaster_id), services=SimpleNamespace(chat_identity=chat_identity))
    service = TimerService(bot, broadcasters=None, broadcaster_settings=None)
    key = service._timed_announcement_key("channel-1", 0)
    service.timed_last_announcements[key] = 0
    service.timed_message_counts[key] = 29
    monkeypatch.setattr("bot.services.stream.timers.get_active_profile", lambda broadcaster_id: profile)

    await service.check_timed_announcements("channel-1", "MeinyaYozakura", 3600)

    chat_identity.send_announcement.assert_not_awaited()
    service.timed_message_counts[key] = 30
    await service.check_timed_announcements("channel-1", "MeinyaYozakura", 3600)

    chat_identity.send_announcement.assert_awaited_once()
    assert chat_identity.send_announcement.await_args.args[1:] == ("Support Mei on YouTube!", "red")
    assert service.timed_message_counts[key] == 0
    assert service.timed_last_announcements[key] == 3600
