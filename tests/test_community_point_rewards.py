from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.shared.events.community as community


def create_bot():
    services = SimpleNamespace(
        features=SimpleNamespace(is_enabled=MagicMock(return_value=True)),
        points=SimpleNamespace(add_points=AsyncMock()),
        stream_logs=SimpleNamespace(write=MagicMock())
    )
    return SimpleNamespace(services=services)


@pytest.mark.asyncio
async def test_subscription_reward_is_awarded_silently(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(subscription_reward=500))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        user=SimpleNamespace(id="viewer-1", name="viewer")
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_subscription_points(bot, payload)

    assert awarded == 500
    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 500)
    bot.services.stream_logs.write.assert_called_once()


@pytest.mark.asyncio
async def test_cheer_reward_requires_minimum_bits(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=200, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        cheer=SimpleNamespace(bits=99)
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_cheer_points(bot, payload)

    assert awarded == 0
    bot.services.points.add_points.assert_not_awaited()
    bot.services.stream_logs.write.assert_not_called()


@pytest.mark.asyncio
async def test_cheer_reward_is_fixed_for_qualifying_event(monkeypatch) -> None:
    bot = create_bot()
    profile = SimpleNamespace(points=SimpleNamespace(cheer_reward=200, cheer_minimum_bits=100))
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        cheer=SimpleNamespace(bits=500)
    )
    monkeypatch.setattr(community, "get_active_profile", lambda broadcaster_id: profile)

    awarded = await community.award_cheer_points(bot, payload)

    assert awarded == 200
    bot.services.points.add_points.assert_awaited_once_with("channel-1", "viewer-1", "viewer", 200)
    bot.services.stream_logs.write.assert_called_once()
