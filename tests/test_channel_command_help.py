import pytest
from twitchio.ext import commands

from bot.component_loader import GLOBAL_COMPONENTS
from bot.profiles import ChannelProfile, FeatureName, GlobalCommandDefaults, LeagueConfig, OverwatchConfig, PointsConfig, ProfileFeatureName, RaidBossConfig, activate_profile, clear_profiles
from bot.services.channels.feature_toggle import FeatureToggleService
from web.channel.command_help import build_command_help_groups, build_enabled_command_help_groups


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
    assert get_command(points, "!shards give <username> <amount>").enabled is True
    assert len(points.commands) == 9


@pytest.mark.parametrize(("channel_name", "expected_group"), [("MeinyaYozakura", "Channel-specific")])
def test_command_help_includes_profile_specific_groups(channel_name: str, expected_group: str) -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name=channel_name)
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)

    assert expected_group in {group.name for group in groups}


def test_command_help_includes_configured_overwatch_commands() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="Milky_GalaxyVT", overwatch=OverwatchConfig(player_id="Milky#123"))
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)
    overwatch = get_group(groups, "Overwatch")

    assert [command.syntax for command in overwatch.commands] == ["!ow", "!owrank", "!owrecord <win|loss>", "!owreset"]


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


def test_profile_feature_toggle_disables_integration_command_help() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel", league=LeagueConfig(enabled=True))
    activate_profile(broadcaster_id, profile)
    features = FeatureToggleService(db=None)
    features.overrides[broadcaster_id] = {features.profile_feature_key(ProfileFeatureName.LEAGUE): False}
    league = get_group(build_command_help_groups(features, broadcaster_id, profile), "League of Legends")

    assert all(not command.enabled for command in league.commands)


def test_command_help_includes_raid_boss_commands_for_enabled_profiles() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel", raid_bosses=RaidBossConfig(enabled=True))
    activate_profile(broadcaster_id, profile)
    groups = build_command_help_groups(FeatureToggleService(db=None), broadcaster_id, profile)
    raid_bosses = get_group(groups, "Raid bosses")

    assert [command.syntax for command in raid_bosses.commands] == [
        "!raid",
        "!raid attack",
        "!raid shop",
        "!raid buy <item>",
        "!raid equip <weapon>",
        "!raid inventory",
        "!raid repair <weapon>",
        "!raid leaderboard",
        "!raid spawn <tutorial|mini|main> <type|random>",
        "!raid end"
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

    assert get_command(raid_bosses, "!raid nextstream").permission == "Broadcaster/mod"


def test_command_help_marks_commands_disabled_when_channel_profile_is_off() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel")
    activate_profile(broadcaster_id, profile)
    features = FeatureToggleService(db=None)
    features.overrides[broadcaster_id] = {features.feature_key(FeatureName.CHANNEL): False}
    groups = build_command_help_groups(features, broadcaster_id, profile)

    assert all(not command.enabled for group in groups for command in group.commands)


def test_enabled_command_help_omits_disabled_commands_and_empty_groups() -> None:
    broadcaster_id = "channel-1"
    profile = ChannelProfile(channel_name="channel", globals=GlobalCommandDefaults(height=False), league=LeagueConfig(enabled=True))
    activate_profile(broadcaster_id, profile)
    features = FeatureToggleService(db=None)
    features.overrides[broadcaster_id] = {features.profile_feature_key(ProfileFeatureName.LEAGUE): False}
    groups = build_enabled_command_help_groups(features, broadcaster_id, profile)

    assert "!height [username]" not in {command.syntax for group in groups for command in group.commands}
    assert "!pp [username]" in {command.syntax for group in groups for command in group.commands}
    assert "League of Legends" not in {group.name for group in groups}


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
        "raid", "ow", "owrank", "owrecord", "owreset"
    }
    assert shared_command_names - profile_specific_commands <= catalog_names
