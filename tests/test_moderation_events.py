from types import SimpleNamespace

import pytest

from bot.component_loader import GLOBAL_COMPONENTS
from bot.shared.events.moderation import ModerationEvents
from config.settings import settings


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
