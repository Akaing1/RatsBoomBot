from types import SimpleNamespace

import asqlite
import pytest

from bot.profiles import ChannelProfile, FirstChatShoutout, activate_profile, clear_profiles
from bot.services.stream.first_chat_shoutouts import FirstChatShoutoutService


class FakeShoutouts:

    def __init__(self):
        self.messages = []
        self.queued = []

    async def send_chat_message(self, broadcaster_id, username, template=None):
        self.messages.append((broadcaster_id, username, template))
        return True

    def enqueue(self, **values):
        self.queued.append(values)
        return True, "queued", 1


@pytest.mark.asyncio
async def test_configured_user_is_shouted_out_once_per_stream(tmp_path) -> None:
    database_path = tmp_path / "first-chat.db"
    shoutouts = FakeShoutouts()
    stream_logs = SimpleNamespace(active_sessions={"channel-1": SimpleNamespace(stream_id="stream-1")})
    profile = ChannelProfile(
        channel_name="channel",
        first_chat_shoutouts=(
            FirstChatShoutout(user_id="user-1", username="alice", message="Custom {username}"),
        )
    )
    activate_profile("channel-1", profile)

    try:
        async with asqlite.create_pool(str(database_path)) as database:
            service = FirstChatShoutoutService(None, database, shoutouts, stream_logs)
            await service.setup()

            first = await service.handle_message(broadcaster_id="channel-1", user_id="user-1", username="alice")
            duplicate = await service.handle_message(broadcaster_id="channel-1", user_id="user-1", username="alice")

            assert first is True
            assert duplicate is False
            assert shoutouts.messages == [("channel-1", "alice", "Custom {username}")]
            assert len(shoutouts.queued) == 1
    finally:
        clear_profiles()


@pytest.mark.asyncio
async def test_first_chat_marker_survives_service_restart(tmp_path) -> None:
    database_path = tmp_path / "first-chat.db"
    shoutouts = FakeShoutouts()
    stream_logs = SimpleNamespace(active_sessions={"channel-1": SimpleNamespace(stream_id="stream-1")})
    activate_profile(
        "channel-1",
        ChannelProfile(
            channel_name="channel",
            first_chat_shoutouts=(FirstChatShoutout(user_id="user-1", username="alice"),)
        )
    )

    try:
        async with asqlite.create_pool(str(database_path)) as database:
            first_service = FirstChatShoutoutService(None, database, shoutouts, stream_logs)
            await first_service.setup()
            assert await first_service.handle_message(broadcaster_id="channel-1", user_id="user-1", username="alice") is True

            restarted_service = FirstChatShoutoutService(None, database, shoutouts, stream_logs)
            await restarted_service.setup()
            assert await restarted_service.handle_message(broadcaster_id="channel-1", user_id="user-1", username="alice") is False
    finally:
        clear_profiles()
