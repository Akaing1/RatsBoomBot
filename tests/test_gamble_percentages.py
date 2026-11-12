from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.profiles import PointsConfig
from bot.shared.commands.points import PointsCommandHandler


@pytest.mark.asyncio
@pytest.mark.parametrize('amount,balance,bet', [
    ('20%', 1000, 200), ('20%', 999, 199), ('1%', 100, 1),
    ('100%', 999, 999), ('all', 999, 999), ('50', 999, 50),
])
@pytest.mark.parametrize('won', [True, False])
async def test_gamble_amount_settlement(monkeypatch, amount, balance, bet, won):
    points = SimpleNamespace(get_points=AsyncMock(return_value=balance), settle_wager=AsyncMock(return_value=100))
    handler = PointsCommandHandler(SimpleNamespace(services=SimpleNamespace(points=points)))
    config = PointsConfig()
    handler.get_context = AsyncMock(return_value=('channel', config))
    handler.send_message = AsyncMock()
    ctx = SimpleNamespace(chatter=SimpleNamespace(id='viewer', name='viewer'), broadcaster=SimpleNamespace(id='channel'))
    monkeypatch.setattr('bot.shared.commands.points.random.random', lambda: 0 if won else 1)

    await handler.gamble(ctx, amount, 'points')

    assert points.settle_wager.await_args.kwargs['bet'] == bet
    assert points.settle_wager.await_args.kwargs['payout'] == (bet * 2 if won else 0)
    if amount in ('100%', 'all'):
        assert handler.send_message.await_args.args[1] == (config.messages.gamble_all_win if won else config.messages.gamble_all_loss)


@pytest.mark.asyncio
@pytest.mark.parametrize('amount,balance', [
    ('0%', 100), ('101%', 100), ('-20%', 100), ('20.5%', 100),
    ('nan%', 100), ('%', 100), ('20%%', 100), ('1%', 99), ('20%', 0),
    ('9' * 5000 + '%', 100),
])
async def test_invalid_or_zero_percentage_never_places_wager(amount, balance):
    points = SimpleNamespace(get_points=AsyncMock(return_value=balance), settle_wager=AsyncMock())
    handler = PointsCommandHandler(SimpleNamespace(services=SimpleNamespace(points=points)))
    handler.get_context = AsyncMock(return_value=('channel', PointsConfig()))
    handler.send_message = AsyncMock()
    ctx = SimpleNamespace(chatter=SimpleNamespace(id='viewer', name='viewer'), broadcaster=SimpleNamespace(id='channel'))

    await handler.gamble(ctx, amount, 'points')

    points.settle_wager.assert_not_awaited()
    handler.send_message.assert_awaited_once()
