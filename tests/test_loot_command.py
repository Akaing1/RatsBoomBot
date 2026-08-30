from types import SimpleNamespace

import pytest

from bot.profiles import ChannelProfile, FeatureDefaults, RaidBossConfig, activate_profile, clear_profiles
from bot.services.engagement.raid_boss import RaidAttackResult, RaidBossEvent
from bot.shared.commands.raid_boss import RaidBossCommands


class FakeLootService:

    async def get_latest_loot(self, broadcaster_id, user_id):
        return {
            "boss_name": "Striking Dummy",
            "contribution_points": 100,
            "final_hit_points": 1000,
            "bonus_points": 5000,
            "total_points": 6100,
            "items": ()
        }


class FakeContext:

    def __init__(self):
        self.broadcaster = SimpleNamespace(id="channel-1")
        self.chatter = SimpleNamespace(id="user-1", name="alice")
        self.replies = []

    async def reply(self, message):
        self.replies.append(message)

    async def send(self, message):
        self.replies.append(message)


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


@pytest.mark.asyncio
async def test_loot_command_shows_latest_personal_raid_rewards() -> None:
    features = SimpleNamespace(is_enabled=lambda broadcaster_id, feature: True)
    bot = SimpleNamespace(services=SimpleNamespace(features=features, raid_bosses=FakeLootService()))
    profile = ChannelProfile(channel_name="channel", features=FeatureDefaults(points=True, raid_bosses=True), raid_bosses=RaidBossConfig(enabled=True))
    activate_profile("channel-1", profile)
    command = RaidBossCommands(bot)
    context = FakeContext()

    await command.loot.callback(command, context)

    assert context.replies == ["Your loot from Striking Dummy: 6,100 points | 1,000 final-hit bonus | 5,000 bonus loot points."]


@pytest.mark.asyncio
async def test_defeated_raid_uses_green_announcement() -> None:
    event = RaidBossEvent(1, "Striking Dummy", "melee", "tutorial", 10000, 100, 5000, "active", 2, 1)
    announcements = []

    class FakeCompletedRaidService:

        async def get_active_event(self, broadcaster_id):
            return event

        async def register_stream(self, broadcaster_id, stream_id):
            return event, 0

        async def attack(self, *args):
            return RaidAttackResult(100, 0, "Striking Dummy", None, False, True, reward=5000)

        async def send_announcement(self, broadcaster_id, message, color):
            announcements.append((broadcaster_id, message, color))

    features = SimpleNamespace(is_enabled=lambda broadcaster_id, feature: True)
    stream_logs = SimpleNamespace(active_sessions={"channel-1": SimpleNamespace(stream_id="stream-1")})
    bot = SimpleNamespace(services=SimpleNamespace(features=features, raid_bosses=FakeCompletedRaidService(), stream_logs=stream_logs))
    profile = ChannelProfile(channel_name="channel", features=FeatureDefaults(points=True, raid_bosses=True), raid_bosses=RaidBossConfig(enabled=True))
    activate_profile("channel-1", profile)
    command = RaidBossCommands(bot)
    context = FakeContext()

    await command.attack.callback(command, context)

    assert announcements == [("channel-1", "@alice dealt the final 100 damage and defeated Striking Dummy! The 5,000-point reward pool has been distributed by contribution!", "green")]
