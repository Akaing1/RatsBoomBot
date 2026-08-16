from types import SimpleNamespace

import pytest

from bot.profiles import ChannelProfile, FeatureDefaults, RaidMessages, activate_profile, clear_profiles
from bot.shared.commands.raids import RaidCommands


class FakeRaidBroadcaster:

    def __init__(self):
        self.targets = []

    async def start_raid(self, target) -> None:
        self.targets.append(target)


class FakeContext:

    def __init__(self, broadcaster_id: str, chatter_id: str):
        self.broadcaster = SimpleNamespace(id=broadcaster_id)
        self.chatter = SimpleNamespace(id=chatter_id, name="broadcaster")
        self.messages = []
        self.replies = []

    async def send(self, message: str) -> None:
        self.messages.append(message)

    async def reply(self, message: str) -> None:
        self.replies.append(message)


class FakeFeatures:

    @staticmethod
    def is_enabled(broadcaster_id, feature) -> bool:
        return True


class FakeBot:

    def __init__(self):
        self.raid_broadcaster = FakeRaidBroadcaster()
        self.services = SimpleNamespace(features=FakeFeatures())
        self.target = SimpleNamespace(id="target-1", name="targetchannel")

    async def fetch_user(self, *, login: str):
        return self.target if login == self.target.name else None

    def create_partialuser(self, broadcaster_id: str):
        return self.raid_broadcaster


@pytest.fixture(autouse=True)
def clear_active_profiles():
    clear_profiles()
    yield
    clear_profiles()


@pytest.mark.asyncio
async def test_start_raid_sends_both_profile_messages() -> None:
    bot = FakeBot()
    commands = RaidCommands(bot)
    context = FakeContext("channel-1", "channel-1")
    profile = ChannelProfile(
        channel_name="broadcaster",
        features=FeatureDefaults(raid_responses=True),
        raid_messages=RaidMessages(
            outgoing="Raid @{target_name}!",
            outgoing_subscriber="Subscriber raid @{target_name}!"
        )
    )
    activate_profile("channel-1", profile)

    await commands.start_raid.callback(commands, context, "targetchannel")

    assert bot.raid_broadcaster.targets == [bot.target]
    assert context.messages == ["Raid @targetchannel!", "Subscriber raid @targetchannel!"]
    assert context.replies == []


@pytest.mark.asyncio
async def test_start_raid_is_broadcaster_only() -> None:
    bot = FakeBot()
    commands = RaidCommands(bot)
    context = FakeContext("channel-1", "viewer-1")

    await commands.start_raid.callback(commands, context, "targetchannel")

    assert bot.raid_broadcaster.targets == []
    assert context.replies == ["Only the broadcaster can start a raid."]


@pytest.mark.asyncio
async def test_start_raid_requires_both_messages() -> None:
    bot = FakeBot()
    commands = RaidCommands(bot)
    context = FakeContext("channel-1", "channel-1")
    profile = ChannelProfile(channel_name="broadcaster", raid_messages=RaidMessages(outgoing="Raid @{target_name}!"))
    activate_profile("channel-1", profile)

    await commands.start_raid.callback(commands, context, "targetchannel")

    assert bot.raid_broadcaster.targets == []
    assert context.replies == ["Both outgoing raid messages must be configured before starting a raid."]
