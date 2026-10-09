from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.profiles import ChannelProfile, PointsConfig, activate_profile, clear_profiles
from bot.shared.commands.pets import PetsCommands


@pytest.fixture(autouse=True)
def profiles():
    clear_profiles()
    activate_profile('channel', ChannelProfile(channel_name='channel', points=PointsConfig(display_name='Shards')))
    activate_profile('source', ChannelProfile(channel_name='source', points=PointsConfig(display_name='Cookies')))
    yield
    clear_profiles()


def setup_command():
    pet = SimpleNamespace(display_name='Little Rat', rarity='common', passive_percent_label='10', passive_description='bonus loyalty points earned')
    service = SimpleNamespace(
        buy_ticket=AsyncMock(return_value=50_000),
        get_equipped_pet=AsyncMock(return_value=pet),
        ticket_count=AsyncMock(return_value=1),
        equip=AsyncMock(return_value=pet),
        summon=AsyncMock(return_value=SimpleNamespace(display_name='Little Rat', rarity='common', duplicate=True, refund=12_500, refund_channel='source')),
    )
    features = SimpleNamespace(is_global_command_enabled=lambda *_: True, is_enabled=lambda *_: True)
    bot = SimpleNamespace(services=SimpleNamespace(pets=service, features=features, chatter_stats=SimpleNamespace(resolve_identity=AsyncMock(return_value=None))))
    ctx = SimpleNamespace(broadcaster=SimpleNamespace(id='channel'), chatter=SimpleNamespace(id='viewer', name='alice'), reply=AsyncMock())
    return PetsCommands(bot), ctx, service


@pytest.mark.asyncio
async def test_purchase_responses_use_channel_currency():
    command, ctx, service = setup_command()
    await command.buy.callback(command, ctx, item='ticket')
    assert ctx.reply.call_args.args[0] == 'Bought 1 summon ticket for 50,000 Shards. Use !pets summon. See rates and current collection using !pets'
    await command.buy.callback(command, ctx, item='invalid')
    assert '50,000 Shards:' in ctx.reply.call_args.args[0]
    service.buy_ticket.side_effect = ValueError('You need 50,000 loyalty points in this channel to buy a summon ticket.')
    await command.buy.callback(command, ctx, item='ticket')
    assert '50,000 Shards' in ctx.reply.call_args.args[0]
    command.bot.services.features.is_enabled = lambda *_: False
    await command.buy.callback(command, ctx, item='ticket')
    assert ctx.reply.call_args.args[0] == 'Shards are disabled in this channel.'


@pytest.mark.asyncio
async def test_summon_error_and_cross_channel_refund_currency():
    command, ctx, service = setup_command()
    await command.summon.callback(command, ctx)
    assert "12,500 Cookies has been gifted as compensation." in ctx.reply.call_args.args[0]
    service.summon.side_effect = ValueError('You have no summon tickets. Buy one with !pets buy ticket (50,000 points).')
    await command.summon.callback(command, ctx)
    assert '(50,000 Shards)' in ctx.reply.call_args.args[0]


@pytest.mark.asyncio
async def test_status_and_equip_passive_use_channel_currency():
    command, ctx, _ = setup_command()
    await command.pets.callback(command, ctx)
    assert '10% bonus Shards earned' in ctx.reply.call_args.args[0]
    await command.equip.callback(command, ctx, name='Little Rat')
    assert '10% bonus Shards earned' in ctx.reply.call_args.args[0]


def test_currency_fallback_and_literal_currency_name():
    command, _, _ = setup_command()
    assert command.currency_name('unknown') == 'Points'
    activate_profile('channel', ChannelProfile(channel_name='channel', points=PointsConfig(display_name='Star points')))
    assert command.currency_text('50,000 loyalty points', 'channel') == '50,000 Star points'


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['Little Rat', 'Silly Bat', 'Sleepy Fox'])
async def test_equip_parser_preserves_full_pet_name(text):
    from twitchio.ext.commands.view import StringView
    command, ctx, service = setup_command()
    ctx._view = StringView(text)
    _, kwargs = await command.equip._parse_arguments(ctx)
    await command.equip.callback(command, ctx, **kwargs)
    service.equip.assert_awaited_once_with('viewer', text)
    assert ctx.reply.call_args.args[0] == 'Little Rat equipped: 10% bonus Shards earned.'
