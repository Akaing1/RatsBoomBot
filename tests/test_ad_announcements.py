from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from bot.services.stream.ad_announcements import AdAnnouncementService


class FakeBroadcaster:

    def __init__(self, next_ad_at):
        self.next_ad_at = next_ad_at
        self.announcements = []
        self.messages = []
        self.schedule_fetches = 0

    async def fetch_ad_schedule(self):
        self.schedule_fetches += 1
        return SimpleNamespace(next_ad_at=self.next_ad_at)

    async def send_announcement(self, *, moderator, message: str, color: str) -> None:
        self.announcements.append({"moderator": moderator, "message": message, "color": color})

    async def send_message(self, *, sender, message: str) -> None:
        self.messages.append(message)


class FakeBroadcasterService:

    async def get_live_broadcasters(self):
        return {"channel-1": "channel"}


class FakeBot:

    def __init__(self, broadcaster, ad_announcements_enabled=True):
        self.broadcaster = broadcaster
        self.services = SimpleNamespace(
            features=SimpleNamespace(
                is_enabled=lambda broadcaster_id, feature: ad_announcements_enabled
            )
        )
        self.user = SimpleNamespace(id="bot-1")

    def create_partialuser(self, broadcaster_id: str):
        return self.broadcaster


@pytest.mark.asyncio
async def test_ad_warning_is_sent_between_one_and_two_minutes_before_ad() -> None:
    broadcaster = FakeBroadcaster(datetime.now(UTC) + timedelta(seconds=110))
    service = AdAnnouncementService(FakeBot(broadcaster), FakeBroadcasterService())

    await service.check_ad_schedules()

    assert len(broadcaster.announcements) == 1
    assert broadcaster.announcements[0]["moderator"] == "channel-1"
    assert broadcaster.announcements[0]["color"] == "purple"
    assert "Ads starting in ~" in broadcaster.announcements[0]["message"]
    assert broadcaster.messages == []


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
