import pytest
from twitchio.ext import commands

from bot.component_loader import GLOBAL_COMPONENTS
from bot.profiles import ChannelProfile, FeatureName, GlobalCommandDefaults, LeagueConfig, PointsConfig, RaidBossConfig, activate_profile, clear_profiles
from bot.services.channels.feature_toggle import FeatureToggleService
from web.channel.command_help import build_command_help_groups


@pytest.fixture(autouse=True)
def reset_active_profiles():
    clear_profiles()
    yield
    clear_profiles()


def get_group(groups, name: str):
    return next(group for group in groups if group.name == name)


def get_command(group, syntax: str):
    return next(command for command in group.commands if command.syntax == syntax)


def test_command_help_uses_profile_currency_and_effective_toggle_states() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(
        channel_name="channel",
        globals=GlobalCommandDefaults(height=False),
        points=PointsConfig(command_name="shards")
    )
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)

    utility = get_group(groups, "Utility")
    points = get_group(groups, "Points")

    assert get_command(utility, "!height [username]").enabled is False
    assert get_command(utility, "!pp [username]").enabled is True
    assert get_command(points, "!shards [username]").enabled is True
    assert len(points.commands) == 8


@pytest.mark.parametrize(("channel_name", "expected_group"), [
    ("MeinyaYozakura", "Channel-specific"),
    ("Milky_GalaxyVT", "Overwatch")
])
def test_command_help_includes_profile_specific_groups(channel_name: str, expected_group: str) -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name=channel_name)
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)

    assert expected_group in {group.name for group in groups}


def test_command_help_includes_league_commands_for_enabled_profiles() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel", league=LeagueConfig(enabled=True))
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)
    league = get_group(groups, "League of Legends")

    assert [command.syntax for command in league.commands] == [
        "!champs",
        "!champs <champion>",
        "!register <Riot ID> [region]",
        "!unregister",
        "!rank [chatter]",
        "!ladder"
    ]


def test_command_help_includes_raid_boss_commands_for_enabled_profiles() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel", raid_bosses=RaidBossConfig(enabled=True))
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)
    raid_bosses = get_group(groups, "Raid bosses")

    assert [command.syntax for command in raid_bosses.commands] == [
        "!boss",
        "!attack",
        "!raidshop",
        "!buy <item>",
        "!equip <weapon>",
        "!inventory",
        "!raiders",
        "!spawnboss <type|random>",
        "!endboss"
    ]


def test_raid_boss_toggle_is_hidden_for_unconfigured_profiles() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel")
    activate_profile(broadcaster_id, profile)
    features = FeatureToggleService(db=None).get_channel_features(broadcaster_id)

    assert FeatureName.RAID_BOSSES not in features


def test_command_help_includes_offline_control_only_when_configured() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel", raid_bosses=RaidBossConfig(enabled=True, offline_testing_enabled=True))
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)
    raid_bosses = get_group(groups, "Raid bosses")

    assert get_command(raid_bosses, "!nextraidstream").permission == "Broadcaster/mod"


def test_command_help_marks_commands_disabled_when_channel_profile_is_off() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel")
    activate_profile(broadcaster_id, profile)
    features = FeatureToggleService(db=None)
    features.overrides[broadcaster_id] = {features.feature_key(FeatureName.CHANNEL): False}
    groups = build_command_help_groups(features, broadcaster_id, profile)

    assert all(not command.enabled for group in groups for command in group.commands)


def test_command_help_catalog_covers_every_shared_top_level_command() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel")
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)
    catalog_names = {command.syntax.removeprefix("!").split()[0] for group in groups for command in group.commands}
    shared_command_names = {
        command.name
        for component in GLOBAL_COMPONENTS
        for command in component.__dict__.values()
        if isinstance(command, commands.Command) and command.parent is None
    }

    profile_specific_commands = {
        "points", "champs", "register", "unregister", "rank", "ladder",
        "explode", "reklop", "randy", "bark", "car",
        "boss", "attack", "raidshop", "buy", "equip", "inventory", "raiders", "spawnboss", "endboss", "nextraidstream"
    }
    assert shared_command_names - profile_specific_commands <= catalog_names
