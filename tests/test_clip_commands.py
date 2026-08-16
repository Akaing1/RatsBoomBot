from types import SimpleNamespace

import pytest

from bot.profiles import ChannelProfile, ClipConfig, GlobalCommandDefaults, activate_profile, clear_profiles
from bot.services.engagement.clips import ClipOnCooldownError, ClipService
from bot.shared.commands.clips import ClipCommands


class FakeClipBroadcaster:

    def __init__(self):
        self.requests = []

    async def create_clip(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(id="clip-1")


class FakeClipBot:

    def __init__(self):
        self.broadcaster = FakeClipBroadcaster()
        self.clip = SimpleNamespace(id="clip-1", url="https://clips.twitch.tv/clip-1")

    def create_partialuser(self, broadcaster_id: str):
        return self.broadcaster

    async def _clips(self):
        yield self.clip

    def fetch_clips(self, **kwargs):
        return self._clips()


class FakeFeatures:

    @staticmethod
    def is_global_group_enabled(broadcaster_id, group) -> bool:
        return True


class FakeClipCommandsService:

    def __init__(self):
        self.requests = []

    async def create_clip(self, broadcaster_id, channel_name, username, duration, config):
        self.requests.append((broadcaster_id, channel_name, username, duration, config))
        return SimpleNamespace(id="clip-1")

    async def wait_for_clip(self, broadcaster_id, clip_id, timeout_seconds):
        return SimpleNamespace(id=clip_id, url="https://clips.twitch.tv/clip-1")


class FakeCommandBot:

    def __init__(self):
        self.clip_service = FakeClipCommandsService()
        self.services = SimpleNamespace(features=FakeFeatures(), clips=self.clip_service)


class FakeContext:

    def __init__(self):
        self.broadcaster = SimpleNamespace(id="channel-1")
        self.chatter = SimpleNamespace(name="alice")
        self.messages = []
        self.replies = []

    async def send(self, message: str) -> None:
        self.messages.append(message)

    async def reply(self, message: str) -> None:
        self.replies.append(message)


@pytest.fixture(autouse=True)
def clear_active_profiles():
    clear_profiles()
    yield
    clear_profiles()


@pytest.mark.asyncio
async def test_clip_service_creates_requested_duration_and_enforces_cooldown() -> None:
    bot = FakeClipBot()
    service = ClipService(bot)
    config = ClipConfig(cooldown_seconds=120)

    created = await service.create_clip("channel-1", "channel", "alice", 60, config)
    clip = await service.wait_for_clip("channel-1", created.id, 15)

    assert bot.broadcaster.requests == [{
        "token_for": "channel-1",
        "title": "channel clipped by alice",
        "duration": 60.0
    }]
    assert clip.url == "https://clips.twitch.tv/clip-1"

    with pytest.raises(ClipOnCooldownError) as error:
        await service.create_clip("channel-1", "channel", "bob", 30, config)

    assert error.value.remaining_seconds == 120


@pytest.mark.asyncio
@pytest.mark.parametrize(("option", "duration"), [(None, 60), ("short", 30)])
async def test_clip_command_supports_full_and_short_clips(option, duration) -> None:
    bot = FakeCommandBot()
    command = ClipCommands(bot)
    context = FakeContext()
    profile = ChannelProfile(channel_name="channel", globals=GlobalCommandDefaults(enabled=True, clips=True))
    activate_profile("channel-1", profile)

    await command.clip.callback(command, context, option)

    assert bot.clip_service.requests[0][3] == duration
    assert context.replies == [f"Creating a {duration}-second clip for @alice..."]
    assert context.messages == ["@alice caught that! https://clips.twitch.tv/clip-1"]


@pytest.mark.asyncio
async def test_clip_command_rejects_unknown_option() -> None:
    bot = FakeCommandBot()
    command = ClipCommands(bot)
    context = FakeContext()
    activate_profile("channel-1", ChannelProfile(channel_name="channel"))

    await command.clip.callback(command, context, "long")

    assert bot.clip_service.requests == []
    assert context.replies == ["Use !clip for 60 seconds or !clip short for 30 seconds."]
