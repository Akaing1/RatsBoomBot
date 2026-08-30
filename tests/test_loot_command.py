from types import SimpleNamespace

import pytest

from bot.profiles import ChannelProfile, FeatureDefaults, RaidBossConfig, activate_profile, clear_profiles
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
