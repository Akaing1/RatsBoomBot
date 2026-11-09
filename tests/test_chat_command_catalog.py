from types import SimpleNamespace
from unittest.mock import Mock

from bot.profiles import ChannelProfile, GlobalCommandGroup
from web.channel.chat_commands import chat_command_catalog


def features():
    return SimpleNamespace(is_enabled=Mock(return_value=True), is_global_group_enabled=Mock(return_value=True),
                           is_global_command_enabled=Mock(return_value=True), is_profile_feature_enabled=Mock(return_value=True))


def test_catalog_reuses_registered_subcommands_and_aliases():
    catalog = chat_command_catalog(features(), '1', ChannelProfile(channel_name='example'))
    syntax = {command['syntax'] for command in catalog}
    assert '!set slowmode on|off' in syntax
    assert '!socials twitter' in syntax
    assert '!rollall [username]' in syntax
    assert '!points duel accept' in syntax
    assert '!points spin <red|black|green> <amount>' in syntax
    assert '!bark' not in syntax
    assert all(command['value'] == command['syntax'].split()[0] for command in catalog)


def test_catalog_excludes_disabled_commands_and_owner_only_actions_for_moderators():
    flags = features()
    flags.is_global_group_enabled.side_effect = lambda channel, group: group is not GlobalCommandGroup.VIEWER_QUEUE
    catalog = chat_command_catalog(flags, '1', ChannelProfile(channel_name='example'), moderator=True)
    syntax = {command['syntax'] for command in catalog}
    assert '!join' not in syntax
    assert '!points reset' not in syntax
    assert '!points duel accept' in syntax
    assert chat_command_catalog(flags, '1', None) == []
