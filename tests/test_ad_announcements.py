from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from bot.profiles import ChannelProfile, activate_profile, clear_profiles
from bot.services.stream.ad_announcements import AdAnnouncementService


class FakeBroadcaster:

    def __init__(self, next_ad_at):
        self.id = "channel-1"
        self.next_ad_at = next_ad_at
        self.announcements = []
        self.messages = []
        self.schedule_fetches = 0

    async def fetch_ad_schedule(self):
        self.schedule_fetches += 1
        return SimpleNamespace(next_ad_at=self.next_ad_at)

    async def send_announcement(self, *, moderator, message: str, color: str) -> None:
        self.announcements.append({"moderator": moderator, "message": message, "color": color})

    async def send_message(self, *, sender, message: str, reply_to_message_id=None) -> None:
        self.messages.append(message)


class FakeChatIdentity:

    def __init__(self, bot):
        self.bot = bot

    async def send_announcement(self, broadcaster, message, color):
        await broadcaster.send_announcement(moderator=self.bot.user.id, message=message, color=color)

    async def send_message(self, broadcaster, message):
        await broadcaster.send_message(sender=self.bot.user, message=message)


class FakeBroadcasterService:

    async def get_live_broadcasters(self):
        return {"channel-1": "channel"}


class FakeBot:

    def __init__(self, broadcaster, ad_announcements_enabled=True):
        self.broadcaster = broadcaster
        self.services = SimpleNamespace(
            features=SimpleNamespace(
                is_enabled=lambda broadcaster_id, feature: ad_announcements_enabled
            ),
            chat_identity=FakeChatIdentity(self)
        )
        self.user = SimpleNamespace(id="bot-1")

    def create_partialuser(self, broadcaster_id: str):
        return self.broadcaster


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


@pytest.mark.asyncio
async def test_ad_warning_is_sent_between_one_and_two_minutes_before_ad() -> None:
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())

    await service.check_ad_schedules()

    assert len(broadcaster.announcements) == 1
    assert broadcaster.announcements[0]["moderator"] == "bot-1"
    assert broadcaster.announcements[0]["color"] == "purple"
    assert "Ads starting in ~" in broadcaster.announcements[0]["message"]
    assert " seconds" not in broadcaster.announcements[0]["message"]
    assert broadcaster.messages == []


@pytest.mark.asyncio
async def test_ad_warning_uses_profile_message_with_minute_second_countdown() -> None:
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())
    activate_profile("channel-1", ChannelProfile(channel_name="channel", ad_announcement_message="Custom ad starts in {time}!"))

    await service.check_ad_schedules()

    assert len(broadcaster.announcements) == 1
    assert broadcaster.announcements[0]["message"].startswith("Custom ad starts in 1:")


@pytest.mark.asyncio
async def test_ad_schedule_is_not_fetched_when_announcements_are_disabled() -> None:
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))
    service = AdAnnouncementService(FakeBot(broadcaster, ad_announcements_enabled=False), FakeBroadcasterService())

    await service.check_ad_schedules()

    assert broadcaster.schedule_fetches == 0
    assert broadcaster.announcements == []
    assert broadcaster.messages == []


@pytest.mark.asyncio
async def test_ad_warning_waits_until_ad_is_within_two_minutes() -> None:
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=130))
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())

    await service.check_ad_schedules()

    assert broadcaster.messages == []


@pytest.mark.asyncio
async def test_ad_warning_falls_back_to_chat_message_when_announcement_fails() -> None:
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))

    async def reject_announcement(**kwargs):
        raise RuntimeError("Missing announcement authorization")

    broadcaster.send_announcement = reject_announcement
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())

    await service.check_ad_schedules()

    assert len(broadcaster.messages) == 1
    assert "Ads starting in ~" in broadcaster.messages[0]


@pytest.mark.asyncio
async def test_custom_warning_time_normal_message_and_duplicate_suppression():
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=300))
    from unittest.mock import AsyncMock
    broadcasters = SimpleNamespace(get_live_broadcasters=AsyncMock(return_value={"channel-1": "channel"}))
    service = AdAnnouncementService(FakeBot(broadcaster), broadcasters)
    activate_profile('channel-1', ChannelProfile(channel_name='channel', ad_warning_seconds=360,
        ad_message_type='message', ad_announcement_message='Break in {time}.'))
    await service.check_ad_schedules()
    await service.check_ad_schedules()
    assert len(broadcaster.messages) == 1
    assert broadcaster.messages[0].startswith('Break in 4:')
    assert broadcaster.announcements == []
    # Frequent local countdown checks do not increase Helix schedule requests.
    assert broadcaster.schedule_fetches == 1
    broadcasters.get_live_broadcasters.assert_awaited_once()


@pytest.mark.asyncio
async def test_short_warning_and_custom_color():
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())
    activate_profile('channel-1', ChannelProfile(channel_name='channel', ad_warning_seconds=30,
        ad_announcement_color='orange'))
    await service.check_ad_schedules()
    assert broadcaster.announcements == []
    broadcaster.next_ad_at = datetime.now(UTC) + timedelta(seconds=20)
    service._schedule_cache.clear()
    await service.check_ad_schedules()
    assert broadcaster.announcements[0]['color'] == 'orange'


@pytest.mark.asyncio
async def test_failed_chat_delivery_can_retry_and_invalid_profile_template_does_not_crash():
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())
    activate_profile('channel-1', ChannelProfile(channel_name='channel', ad_message_type='message',
        ad_announcement_message='{time.no_such_attribute}'))
    original = broadcaster.send_message
    async def fail(**kwargs):
        raise RuntimeError('temporary failure')
    broadcaster.send_message = fail
    await service.check_ad_schedules()
    assert not service.warned_ads
    broadcaster.send_message = original
    await service.check_ad_schedules()
    assert len(broadcaster.messages) == 1
    assert service.warned_ads
