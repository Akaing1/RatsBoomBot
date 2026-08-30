import asqlite
import pytest

from bot.profiles import ChannelProfile, CommunityMessages, PointsConfig, activate_profile, clear_profiles, create_generic_profile, get_active_profile
from bot.services.channels.profile_settings import ProfileSettingsService


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


def test_generic_profile_starts_with_safe_features() -> None:
    profile = create_generic_profile("new_streamer")

    assert profile.channel_name == "new_streamer"
    assert profile.features.channel is True
    assert profile.features.points is False
    assert profile.features.timers is False
    assert profile.globals.help is True
    assert profile.globals.kamikaze is False


@pytest.mark.asyncio
async def test_profile_override_updates_and_resets_active_profile(tmp_path) -> None:
    database_path = tmp_path / "profiles.db"
    base_profile = ChannelProfile(
        channel_name="developer_ninjakaing",
        points=PointsConfig(points_per_message=25),
        community_messages=CommunityMessages(follow="Original follow")
    )
    activate_profile("channel-1", base_profile)

    async with asqlite.create_pool(str(database_path)) as database:
        service = ProfileSettingsService(database)
        await service.setup()
        service.apply_overrides("channel-1", base_profile)

        await service.set_override("channel-1", "points.points_per_message", "40", "test")
        await service.set_override("channel-1", "community_messages.follow", "Updated {username}", "test")

        effective = get_active_profile("channel-1")
        assert effective.points.points_per_message == 40
        assert effective.community_messages.follow == "Updated {username}"

        await service.clear_override("channel-1", "points.points_per_message", "test")
        assert get_active_profile("channel-1").points.points_per_message == 25


@pytest.mark.asyncio
async def test_developer_profile_migration_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "profiles.db"
    profile = ChannelProfile(channel_name="developer_ninjakaing", timer_messages=("One", "Two"), points=PointsConfig(command_name="ores"))

    async with asqlite.create_pool(str(database_path)) as database:
        service = ProfileSettingsService(database)
        await service.setup()

        assert await service.migrate_developer_profile("channel-1", profile) is True
        assert await service.migrate_developer_profile("channel-1", profile) is False
        assert service.overrides["channel-1"]["timer_messages"] == "One\nTwo"
        assert service.overrides["channel-1"]["points.points_per_message"] == 10
