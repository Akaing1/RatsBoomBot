from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import asyncio
from aiohttp import ClientConnectionError
from twitchio import HTTPException

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


def fake_poll_clock(monkeypatch):
    from bot.services.engagement import clips
    clock = [0.0]
    sleeps = []
    async def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(clips, 'asyncio', SimpleNamespace(
        get_running_loop=lambda: SimpleNamespace(time=lambda: clock[0]),
        timeout=asyncio.timeout, sleep=sleep))
    return clock, sleeps


@pytest.mark.asyncio
async def test_clip_can_finish_after_old_fifteen_second_limit(monkeypatch):
    clock, sleeps = fake_poll_clock(monkeypatch)
    bot = FakeClipBot()
    calls = []
    async def lookup(**kwargs):
        calls.append(kwargs)
        if clock[0] >= 35:
            yield bot.clip
    bot.fetch_clips = lookup
    result = await ClipService(bot).wait_for_clip('new-channel', 'clip-1', ClipConfig().processing_timeout_seconds)
    assert result is bot.clip
    assert 35 <= clock[0] < 60
    assert len(calls) < 20
    assert all(c == {'clip_ids':['clip-1'], 'token_for':'new-channel', 'max_results':1} for c in calls)
    assert max(sleeps) <= 5
    assert bot.broadcaster.requests == []


@pytest.mark.asyncio
async def test_clip_timeout_is_bounded_and_does_not_create_another_clip(monkeypatch):
    clock, _ = fake_poll_clock(monkeypatch)
    bot = FakeClipBot()
    async def empty(**kwargs):
        if False:
            yield
    bot.fetch_clips = empty
    assert await ClipService(bot).wait_for_clip('channel', 'clip-1', 60) is None
    assert clock[0] == 60
    assert bot.broadcaster.requests == []


@pytest.mark.asyncio
async def test_transient_clip_lookup_errors_retry_the_same_id(monkeypatch):
    fake_poll_clock(monkeypatch)
    bot = FakeClipBot()
    errors = [HTTPException(status=503,extra={}), HTTPException(status=429,extra={}), ClientConnectionError('temporary'), TimeoutError()]
    async def lookup(**kwargs):
        if errors:
            raise errors.pop(0)
        yield bot.clip
    bot.fetch_clips = lookup
    assert await ClipService(bot).wait_for_clip('channel', 'clip-1', 60) is bot.clip
    assert bot.broadcaster.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401,403])
async def test_clip_lookup_does_not_retry_permission_errors(status):
    bot = FakeClipBot()
    calls = []
    async def lookup(**kwargs):
        calls.append(kwargs)
        raise HTTPException(status=status, extra={})
        yield
    bot.fetch_clips = lookup
    with pytest.raises(HTTPException):
        await ClipService(bot).wait_for_clip('channel', 'clip-1', 60)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_stalled_clip_lookup_cannot_exceed_processing_deadline():
    bot = FakeClipBot()
    async def lookup(**kwargs):
        await asyncio.Event().wait()
        yield
    bot.fetch_clips = lookup
    result = await asyncio.wait_for(ClipService(bot).wait_for_clip('channel','clip-1',0.01),timeout=1)
    assert result is None


@pytest.mark.asyncio
async def test_unconfirmed_clip_is_not_announced_as_success(caplog):
    bot = FakeCommandBot()
    bot.clip_service.wait_for_clip = AsyncMock(return_value=None)
    command = ClipCommands(bot)
    ctx = FakeContext()
    activate_profile('channel-1', ChannelProfile(channel_name='new-channel'))
    await command.clip.callback(command, ctx)
    bot.clip_service.wait_for_clip.assert_awaited_once_with('channel-1','clip-1',60)
    assert ctx.messages == []
    assert 'Clip Manager' in ctx.replies[-1]
    assert 'https://clips.twitch.tv/' not in ctx.replies[-1]
    assert 'channel-1' in caplog.text
    assert len(bot.clip_service.requests) == 1


@pytest.mark.asyncio
async def test_verification_error_gets_a_reply_instead_of_success():
    bot = FakeCommandBot()
    bot.clip_service.wait_for_clip = AsyncMock(side_effect=HTTPException(status=401,extra={}))
    command = ClipCommands(bot)
    ctx = FakeContext()
    activate_profile('channel-1',ChannelProfile(channel_name='channel'))
    await command.clip.callback(command,ctx)
    assert ctx.messages == []
    assert ctx.replies[-1] == ClipConfig().messages.authorization_required
