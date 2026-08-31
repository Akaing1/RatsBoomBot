import asqlite
import pytest

from bot.profiles import ChannelProfile, CommunityMessages, activate_profile, clear_profiles, create_generic_profile, get_active_profile
from bot.services.channels.profile_settings import PROFILE_SETTINGS_BY_KEY, ProfileSettingsService


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
        community_messages=CommunityMessages(follow="Original follow")
    )
    activate_profile("channel-1", base_profile)

    async with asqlite.create_pool(str(database_path)) as database:
        service = ProfileSettingsService(database)
        await service.setup()
        service.apply_overrides("channel-1", base_profile)

        await service.set_override("channel-1", "community_messages.follow", "Updated {username}", "test")

        effective = get_active_profile("channel-1")
        assert effective.community_messages.follow == "Updated {username}"

        await service.clear_override("channel-1", "community_messages.follow", "test")
        assert get_active_profile("channel-1").community_messages.follow == "Original follow"


@pytest.mark.asyncio
async def test_developer_profile_migration_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "profiles.db"
    profile = ChannelProfile(channel_name="developer_ninjakaing", timer_messages=("One", "Two"))

    async with asqlite.create_pool(str(database_path)) as database:
        service = ProfileSettingsService(database)
        await service.setup()

        assert await service.migrate_developer_profile("channel-1", profile) is True
        assert await service.migrate_developer_profile("channel-1", profile) is False
        assert service.overrides["channel-1"]["timer_messages"] == "One\nTwo"
        assert "points.points_per_message" not in service.overrides["channel-1"]


def test_streamer_editable_settings_protect_points_and_custom_redeems() -> None:
    assert "points.points_per_message" not in PROFILE_SETTINGS_BY_KEY
    assert "points.message_cooldown_seconds" not in PROFILE_SETTINGS_BY_KEY
    assert "redeems.second_title" not in PROFILE_SETTINGS_BY_KEY
    assert "redeems.second_amount" not in PROFILE_SETTINGS_BY_KEY
    assert {
        "redeems.daily_title",
        "redeems.daily_amount",
        "redeems.first_title",
        "redeems.first_amount"
    } <= PROFILE_SETTINGS_BY_KEY.keys()


def test_timer_validation_normalizes_messages_and_enforces_twitch_limit() -> None:
    definition = ProfileSettingsService.get_definition("timer_messages")

    assert ProfileSettingsService.validate_value(definition, " First timer \n\n Second timer ") == "First timer\nSecond timer"

    with pytest.raises(ValueError, match="Each timer message must be 500 characters or fewer"):
        ProfileSettingsService.validate_value(definition, "x" * 501)
