from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.command_registry import SOCIAL_COMMANDS
from bot.profiles import ChannelProfile, GlobalCommandGroup, activate_profile, clear_profiles
from bot.services.channels.broadcaster_settings import BroadcasterSettings, EXTRA_SOCIAL_LINKS
from bot.shared.commands.socials import SocialCommands


@pytest.fixture
def socials():
    profile = ChannelProfile(channel_name='example')
    activate_profile('1', profile)
    settings = BroadcasterSettings('1', discord_url='https://discord.example', youtube_url='https://youtube.example')
    features = SimpleNamespace(is_global_group_enabled=lambda channel, group: True)
    store = SimpleNamespace(get_settings=AsyncMock(return_value=settings))
    bot = SimpleNamespace(services=SimpleNamespace(features=features, broadcaster_settings=store))
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id='1'), chatter=SimpleNamespace(name='viewer'), reply=AsyncMock())
    yield SocialCommands(bot), ctx, settings, features, profile
    clear_profiles()


@pytest.mark.asyncio
@pytest.mark.parametrize('platform,label', EXTRA_SOCIAL_LINKS.items())
async def test_social_links_only_have_group_commands(socials, platform, label):
    component, ctx, settings, _, _ = socials
    url = f'https://example.com/{platform}'
    setattr(settings, f'{platform}_url', url)
    command = component.socials.get_command(platform)
    await command.callback(component, ctx)
    ctx.reply.assert_awaited_once_with(f'{label}: {url}')
    assert not hasattr(component, platform)
    component.bot.services.broadcaster_settings.get_settings.assert_awaited_with('1')
    assert any(command.syntax == f'!socials {platform}' and command.global_group is GlobalCommandGroup.SOCIALS for command in SOCIAL_COMMANDS.commands)
    assert not any(command.syntax == f'!{platform}' for command in SOCIAL_COMMANDS.commands)


@pytest.mark.asyncio
@pytest.mark.parametrize('platform,label', EXTRA_SOCIAL_LINKS.items())
async def test_missing_social_link_and_disabled_group(socials, platform, label):
    component, ctx, _, features, _ = socials
    command = component.socials.get_command(platform)
    await command.callback(component, ctx)
    ctx.reply.assert_awaited_once_with(f'No {label} link has been set for this channel yet.')
    ctx.reply.reset_mock()
    features.is_global_group_enabled = lambda channel, group: False
    await command.callback(component, ctx)
    ctx.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_socials_overview_includes_configured_links_and_preserves_custom_text(socials):
    component, ctx, settings, _, profile = socials
    settings.vgen_url = 'https://vgen.co/example'
    settings.website_url = 'https://example.com'
    profile = replace(profile, social_messages=replace(profile.social_messages, overview='Find me: {discord_url} | {website_url}'))
    activate_profile('1', profile)
    await component.socials.callback(component, ctx)
    ctx.reply.assert_awaited_once_with('Find me: https://discord.example | https://example.com | VGen: https://vgen.co/example')
    ctx.reply.reset_mock()
    activate_profile('1', replace(profile, social_messages=replace(profile.social_messages, overview='')))
    await component.socials.callback(component, ctx)
    ctx.reply.assert_not_awaited()


@pytest.mark.asyncio
async def test_twitch_link_uses_the_channels_identity_and_respects_the_group(socials):
    component, ctx, _, features, _ = socials
    ctx.broadcaster.name = 'the_streamer'
    ctx.chatter.name = 'different_viewer'
    await component.socials_twitch.callback(component, ctx)
    ctx.reply.assert_awaited_once_with('Twitch: https://www.twitch.tv/the_streamer')
    ctx.reply.reset_mock()
    features.is_global_group_enabled = lambda channel, group: False
    await component.socials_twitch.callback(component, ctx)
    ctx.reply.assert_not_awaited()


def test_twitter_aliases_share_x_commands(socials):
    component, _, _, _, _ = socials
    assert not hasattr(component, 'x')
    assert component.socials.get_command('twitter') is component.socials.get_command('x')
    assert not any(command.syntax == '!socials twitter' for command in SOCIAL_COMMANDS.commands)
    assert next(command for command in SOCIAL_COMMANDS.commands if command.syntax == '!socials x').aliases == ('twitter',)
    assert [command.syntax for command in SOCIAL_COMMANDS.commands][:3] == ['!socials', '!socials twitch', '!socials youtube']
