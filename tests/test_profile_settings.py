import asqlite
import pytest

from bot.profiles import ChannelProfile, CommunityMessages, RaidBossConfig, RaidItemNames, activate_profile, clear_profiles, create_generic_profile, get_active_profile
from bot.services.channels.profile_settings import PROFILE_SETTINGS_BY_KEY, ProfileSettingsService


@pytest.fixture(autouse=True)
def reset_profiles():
    clear_profiles()
    yield
    clear_profiles()


def test_generic_profile_starts_with_standard_commands() -> None:
    profile = create_generic_profile("new_streamer")

    assert profile.channel_name == "new_streamer"
    assert profile.features.channel is True
    assert profile.features.points is True
    assert profile.features.timers is False
    assert profile.globals.help is True
    assert profile.globals.kamikaze is True


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
async def test_nested_raid_item_name_override_updates_active_profile(tmp_path) -> None:
    database_path = tmp_path / "profiles.db"
    base_profile = ChannelProfile(
        channel_name="milky_galaxyvt",
        raid_bosses=RaidBossConfig(item_names=RaidItemNames(potion="Pocket Mercy"))
    )
    activate_profile("channel-1", base_profile)

    async with asqlite.create_pool(str(database_path)) as database:
        service = ProfileSettingsService(database)
        await service.setup()
        service.apply_overrides("channel-1", base_profile)

        await service.set_override("channel-1", "raid_bosses.item_names.potion", "Damage Boost", "test")

        assert get_active_profile("channel-1").raid_bosses.item_names.potion == "Damage Boost"


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
    assert "redeems.daily_amount" not in PROFILE_SETTINGS_BY_KEY
    assert "redeems.first_amount" not in PROFILE_SETTINGS_BY_KEY
    assert {
        "redeems.daily_title",
        "redeems.first_title"
    } <= PROFILE_SETTINGS_BY_KEY.keys()


def test_timer_validation_normalizes_messages_and_enforces_twitch_limit() -> None:
    definition = ProfileSettingsService.get_definition("timer_messages")

    assert ProfileSettingsService.validate_value(definition, " First timer \n\n Second timer ") == "First timer\nSecond timer"

    with pytest.raises(ValueError, match="Each timer message must be 500 characters or fewer"):
        ProfileSettingsService.validate_value(definition, "x" * 501)


@pytest.mark.parametrize("value", ["{unknown}", "{username.name}", "{points:1000000}", "{username!r}", "{", "hello\nworld"])
def test_loyalty_responses_reject_invalid_templates(value) -> None:
    definition = ProfileSettingsService.get_definition("points.messages.balance_self")
    with pytest.raises(ValueError):
        ProfileSettingsService.validate_value(definition, value)


@pytest.mark.asyncio
async def test_loyalty_customization_persists_and_preserves_income(tmp_path) -> None:
    base_profile = ChannelProfile(channel_name="example")
    activate_profile("channel-1", base_profile)
    async with asqlite.create_pool(str(tmp_path / "loyalty.db")) as database:
        service = ProfileSettingsService(database)
        await service.setup()
        service.apply_overrides("channel-1", base_profile)
        await service.set_override("channel-1", "points.display_name", "Stale Bread", "test")
        await service.set_override("channel-1", "points.messages.balance_self", "{username}: {points} {currency}", "test")
        for key in ("redeems.daily_amount", "redeems.first_amount", "points.points_per_message", "points.subscription_reward", "points.cheer_reward", "points.gamble_win_chance"):
            with pytest.raises(ValueError):
                await service.set_override("channel-1", key, "999", "test")
        reloaded = ProfileSettingsService(database)
        await reloaded.setup()
        effective = reloaded.apply_overrides("channel-1", base_profile)
        assert effective.points.display_name == "Stale Bread"
        assert effective.points.messages.balance_self.format(username="rat", points=10, currency=effective.points.display_name) == "rat: 10 Stale Bread"
        assert effective.points.points_per_message == base_profile.points.points_per_message
        assert effective.redeems == base_profile.redeems
        await service.clear_override("channel-1", "points.display_name", "test")
        assert get_active_profile("channel-1").points.display_name == "Points"


def test_loyalty_only_allows_five_fields_and_defaults_follow_currency():
    from bot.profiles import PointsConfig, PointsMessages
    from bot.services.channels.profile_settings import LOYALTY_GROUP

    keys = {key for key, definition in PROFILE_SETTINGS_BY_KEY.items() if definition.group == LOYALTY_GROUP}
    assert keys == {"points.display_name", "points.messages.balance_self", "points.messages.balance_other", "points.messages.add_success", "points.messages.give_success"}
    profile = ChannelProfile(channel_name="example", points=PointsConfig(messages=PointsMessages(gamble_win="Old themed response")))
    service = ProfileSettingsService(None)
    service.overrides["channel"] = {"points.display_name": "Bread", "points.messages.gamble_win": "Old saved override", "points.messages.balance_self": "You have {points} {currency}"}
    effective = service.apply_overrides("channel", profile)
    assert effective.points.messages.gamble_win.format(username="rat", amount=10, new_balance=20, currency=effective.points.display_name) == "rat won 10 Bread and now has 20 Bread!"
    assert effective.points.messages.balance_self == "You have {points} {currency}"
    assert effective.points.messages.leaderboard_entry.format(position=1, username="rat", points=20, currency="Bread") == "1. rat: 20 Bread"
    with pytest.raises(ValueError):
        service.get_definition("points.messages.gamble_win")


def test_all_channel_defaults_use_currency_and_follow_name_override():
    from bot.channels import register_channel_profiles
    from bot.profiles import CHANNEL_PROFILES
    register_channel_profiles()
    service = ProfileSettingsService(None)
    for name, profile in CHANNEL_PROFILES.items():
        assert profile.points.display_name
        for field in ("balance_self", "balance_other", "add_success", "give_success"):
            assert "{currency}" in getattr(profile.points.messages, field), (name, field)
        service.overrides[name] = {"points.display_name": "Test Coins"}
        effective = service.apply_overrides(name, profile)
        assert "Test Coins" in effective.points.messages.balance_self.format(username="rat", points=10, currency=effective.points.display_name)
    assert ProfileSettingsService.validate_value(service.get_definition("points.display_name"), "  ") == "Points"


@pytest.mark.asyncio
async def test_seeded_developer_currency_defaults_refresh_but_user_edits_remain(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "defaults.db")) as db:
        service = ProfileSettingsService(db)
        await service.setup()
        async with db.acquire() as connection:
            for field, value, author in [
                ("balance_self", "Old ores response", "developer-profile-migration"),
                ("balance_other", "My saved response", "streamer:123")
            ]:
                await connection.execute("INSERT INTO channel_profile_overrides (broadcaster_id, setting_name, setting_value, updated_by) VALUES (?, ?, ?, ?)", ("123", f"points.messages.{field}", service.serialize_value(value), author))
        await service.load_overrides()
        effective = service.apply_overrides("123", ChannelProfile(channel_name="test"))
        assert effective.points.display_name == "Points"
        assert effective.points.messages.balance_self == "{username}, you have {points} {currency}!"
        assert effective.points.messages.balance_other == "My saved response"
