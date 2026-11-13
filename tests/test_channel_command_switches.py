from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from twitchio.ext.commands.exceptions import CommandNotFound

from bot.bot import ChannelCommandsDisabled, TwitchBot
from bot.shared.commands.counters import CounterCommands


def make_bot(profile_enabled, commands_enabled):
    bot = SimpleNamespace(services=SimpleNamespace(
        features=SimpleNamespace(
            get_profile_enabled=Mock(return_value=profile_enabled),
            get_globals_enabled=Mock(return_value=commands_enabled),
        ),
        command_slowmode=SimpleNamespace(allow=Mock(return_value=True)),
        custom_commands=SimpleNamespace(handle=AsyncMock()),
        counters=SimpleNamespace(increment_counter=AsyncMock(return_value=1)),
    ))
    bot.global_guard = lambda ctx: TwitchBot.global_guard(bot, ctx)
    return bot


@pytest.mark.asyncio
@pytest.mark.parametrize('profile_enabled,commands_enabled', [(False, True), (True, False), (False, False)])
@pytest.mark.parametrize('name', ['explode', 'reklop', 'randy', 'bark', 'car'])
async def test_private_commands_blocked_before_execution(profile_enabled, commands_enabled, name):
    bot = make_bot(profile_enabled, commands_enabled)
    component = CounterCommands(bot)
    command = getattr(component, name)
    ctx = SimpleNamespace(bot=bot, broadcaster=SimpleNamespace(id='channel'), send=AsyncMock())
    with pytest.raises(ChannelCommandsDisabled) as error:
        await command._run_guards(ctx)
        await command.callback(component, ctx)
    bot.services.counters.increment_counter.assert_not_awaited()
    bot.services.command_slowmode.allow.assert_not_called()
    ctx.send.assert_not_awaited()
    await TwitchBot.event_command_error(bot, SimpleNamespace(exception=error.value))


@pytest.mark.asyncio
@pytest.mark.parametrize('profile_enabled,commands_enabled', [(False, True), (True, False), (False, False), (True, True)])
async def test_custom_fallback_respects_both_switches(profile_enabled, commands_enabled):
    bot = make_bot(profile_enabled, commands_enabled)
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id='channel'))
    await TwitchBot.event_command_error(bot, SimpleNamespace(exception=CommandNotFound('custom'), context=ctx))
    assert bot.services.custom_commands.handle.await_count == int(profile_enabled and commands_enabled)


@pytest.mark.asyncio
async def test_enabled_commands_and_channel_isolation():
    bot = make_bot(True, True)
    bot.services.features.get_profile_enabled.side_effect = lambda channel: channel != 'disabled'
    with pytest.raises(ChannelCommandsDisabled):
        await TwitchBot.global_guard(bot, SimpleNamespace(broadcaster=SimpleNamespace(id='disabled')))
    assert await TwitchBot.global_guard(bot, SimpleNamespace(broadcaster=SimpleNamespace(id='enabled')))
    bot.services.command_slowmode.allow.assert_called_once()


@pytest.mark.asyncio
async def test_unavailable_services_or_channel_fail_closed():
    with pytest.raises(ChannelCommandsDisabled):
        await TwitchBot.global_guard(SimpleNamespace(services=None), SimpleNamespace())
    with pytest.raises(ChannelCommandsDisabled):
        await TwitchBot.global_guard(make_bot(True, True), SimpleNamespace())


def test_rat_alias_uses_guarded_counter():
    assert 'rat' in CounterCommands.explode.aliases
