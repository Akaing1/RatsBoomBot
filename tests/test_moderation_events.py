from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
from collections import defaultdict
from unittest.mock import AsyncMock

import pytest
from twitchio.models.eventsub_ import ChannelModerate

from bot.component_loader import GLOBAL_COMPONENTS
from bot.shared.events.moderation import ModerationEvents
from config.settings import settings
from bot.shared.pending_raids import remember_raid


class ModerationServiceStub:

    def __init__(self, recorded: bool = True) -> None:
        self.recorded = recorded
        self.observations = []

    async def observe_external_ban(self, **observation) -> bool:
        self.observations.append(observation)
        return self.recorded


class StreamLogServiceStub:

    def __init__(self) -> None:
        self.entries = []

    def write(self, broadcaster_id: str, event_type: str, message: str) -> None:
        self.entries.append((broadcaster_id, event_type, message))


def create_ban_payload(moderator_id: str | None = None):
    return SimpleNamespace(
        action="ban",
        moderator=SimpleNamespace(id=moderator_id or settings.SERYBOT_USER_ID, name="sery_bot"),
        ban=SimpleNamespace(user=SimpleNamespace(id="user-1", name="spammer"), reason="Spam Detected."),
        broadcaster=SimpleNamespace(id="channel-1")
    )


def test_moderation_events_are_registered_globally() -> None:
    assert ModerationEvents in GLOBAL_COMPONENTS


@pytest.mark.asyncio
async def test_serybot_ban_is_recorded_and_written_to_stream_log(caplog) -> None:
    moderation = ModerationServiceStub()
    stream_logs = StreamLogServiceStub()
    bot = SimpleNamespace(services=SimpleNamespace(moderation=moderation, stream_logs=stream_logs))

    await ModerationEvents(bot).event_mod_action(create_ban_payload())

    assert moderation.observations == [{
        "broadcaster_id": "channel-1",
        "user_id": "user-1",
        "username": "spammer",
        "moderator_id": settings.SERYBOT_USER_ID,
        "moderator_name": "sery_bot",
        "reason": "Spam Detected.",
        "source": "serybot"
    }]
    assert stream_logs.entries == [("channel-1", "MODERATION", "Recorded SeryBot campaign evidence for spammer (user-1) | Reason: Spam Detected.")]
    assert "Observed SeryBot banning spammer" in caplog.text


@pytest.mark.asyncio
async def test_non_serybot_ban_is_ignored() -> None:
    moderation = ModerationServiceStub()
    stream_logs = StreamLogServiceStub()
    bot = SimpleNamespace(services=SimpleNamespace(moderation=moderation, stream_logs=stream_logs))

    await ModerationEvents(bot).event_mod_action(create_ban_payload(moderator_id="different-moderator"))

    assert moderation.observations == []
    assert stream_logs.entries == []


@pytest.mark.asyncio
async def test_native_twitch_raid_and_unraid_update_popup_without_resetting_countdown():
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(
        get_broadcasters=lambda: {"1": SimpleNamespace(viewer_count=8)})))
    events = ModerationEvents(bot)
    target = SimpleNamespace(id="2", name="target", display_name="Target")
    created = datetime.now(UTC)
    payload = SimpleNamespace(action="raid", broadcaster=SimpleNamespace(id="1"),
                              raid=SimpleNamespace(user=target), timestamp=created)
    await events.event_mod_action(payload)
    pending = bot._dashboard_pending_raids["1"]
    assert pending["target_id"] == "2"
    assert pending["viewer_count"] == 8
    assert pending["expires_at"] == created.timestamp() + 90
    payload.timestamp = created + timedelta(seconds=2)
    await events.event_mod_action(payload)
    assert bot._dashboard_pending_raids["1"] is pending
    # The browser/API path arriving after the event also shares the same timer.
    assert remember_raid(bot, "1", target, created) is pending
    payload.action = "unraid"
    payload.unraid = SimpleNamespace(id="3")
    await events.event_mod_action(payload)
    assert bot._dashboard_pending_raids["1"] is pending
    payload.unraid.id = "2"
    await events.event_mod_action(payload)
    assert not bot._dashboard_pending_raids


@pytest.mark.asyncio
async def test_native_raid_for_unconnected_channel_is_ignored():
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(get_broadcasters=lambda: {})))
    await ModerationEvents(bot).event_mod_action(SimpleNamespace(action="raid", broadcaster=SimpleNamespace(id="other")))
    assert not hasattr(bot, "_dashboard_pending_raids")


@pytest.mark.asyncio
async def test_shared_chat_raid_does_not_create_a_raid_in_the_wrong_channel():
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(
        get_broadcasters=lambda: {"1": object()})))
    await ModerationEvents(bot).event_mod_action(SimpleNamespace(
        action="raid", broadcaster=SimpleNamespace(id="1"), source_broadcaster=SimpleNamespace(id="other"),
        raid=SimpleNamespace(user=SimpleNamespace(id="2", name="target"))))
    assert not hasattr(bot, "_dashboard_pending_raids")


@pytest.mark.asyncio
@pytest.mark.parametrize("source_id", [None, "", "1"])
async def test_actual_twitchio_raid_payload_accepts_empty_source_channel(source_id, caplog):
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(
        get_broadcasters=lambda: {"1": SimpleNamespace(viewer_count=8)})))
    data = defaultdict(lambda: None, action="raid", broadcaster_user_id="1",
                       broadcaster_user_login="sender", broadcaster_user_name="Sender",
                       source_broadcaster_user_id=source_id,
                       moderator_user_id="1", moderator_user_login="sender", moderator_user_name="Sender",
                       raid={"user_id": "2", "user_login": "target", "user_name": "Target", "viewer_count": 8})
    payload = ChannelModerate(data, http=None)
    with caplog.at_level("INFO", logger="RatBoomBot"):
        await ModerationEvents(bot).event_mod_action(payload)
    assert bot._dashboard_pending_raids["1"]["login"] == "target"
    assert "Pending raid recorded" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup_fails", [False, True])
async def test_native_raid_loads_profile_picture_without_losing_raid_on_lookup_failure(lookup_fails):
    target = SimpleNamespace(id="2", name="target", display_name="Target")
    image = "https://static-cdn.jtvnw.net/jtv_user_pictures/target.png"
    full_target = SimpleNamespace(**vars(target), profile_image=SimpleNamespace(url=image))
    bot = SimpleNamespace(services=SimpleNamespace(broadcasters=SimpleNamespace(
        get_broadcasters=lambda: {"1": SimpleNamespace(viewer_count=8)})),
        fetch_user=AsyncMock(return_value=full_target, side_effect=RuntimeError("unavailable") if lookup_fails else None))
    created = datetime.now(UTC)
    pending = remember_raid(bot, "1", target, created)
    payload = SimpleNamespace(action="raid", broadcaster=SimpleNamespace(id="1"),
                              raid=SimpleNamespace(user=target), timestamp=created)
    await ModerationEvents(bot).event_mod_action(payload)
    bot.fetch_user.assert_awaited_once_with(id="2")
    assert bot._dashboard_pending_raids["1"] is pending
    assert pending["created_at"] == created.isoformat()
    assert pending["profile_image_url"] == ("" if lookup_fails else image)
    if not lookup_fails:
        await ModerationEvents(bot).event_mod_action(payload)
        bot.fetch_user.assert_awaited_once()
