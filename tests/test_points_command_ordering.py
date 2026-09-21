from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot.shared.commands.points as points_commands
from bot.profiles import PointsConfig
from bot.shared.commands.points import PointsCommandHandler, PointsCommands


@pytest.mark.asyncio
async def test_balance_command_processes_message_reward_before_reading_balance(monkeypatch) -> None:
    events = []

    class Points:
        async def track_message(self, ctx) -> None:
            events.append("reward")

        async def get_points(self, broadcaster_id: str, user_id: str) -> int:
            events.append("balance")
            return 25

    config = SimpleNamespace(
        display_name="Stale Bread",
        command_name="points",
        messages=SimpleNamespace(
            balance_self="{username}, you have {points} {currency}.",
            balance_other="{username} has {points} points."
        )
    )
    services = SimpleNamespace(points=Points())
    bot = SimpleNamespace(services=services)
    ctx = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1", name="channel"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        reply=AsyncMock()
    )

    monkeypatch.setattr(points_commands, "get_context_broadcaster_id", lambda context: "channel-1")
    monkeypatch.setattr(points_commands, "get_active_profile", lambda broadcaster_id: SimpleNamespace(points=config))
    monkeypatch.setattr(points_commands, "is_feature_enabled", lambda bot, context, feature: True)
    monkeypatch.setattr(points_commands, "is_global_group_enabled", lambda bot, context, group: True)

    await PointsCommandHandler(bot).show_balance(ctx, None, "points")

    assert events == ["reward", "balance"]
    ctx.reply.assert_awaited_once_with("viewer, you have 25 Stale Bread.")


@pytest.mark.asyncio
async def test_global_gamble_command_explains_channel_grouped_syntax(monkeypatch) -> None:
    events = []

    class Points:
        async def track_message(self, ctx) -> None:
            events.append("reward")

    config = PointsConfig(display_name="Sakura Petals", command_name="petals")
    bot = SimpleNamespace(services=SimpleNamespace(points=Points()))
    ctx = SimpleNamespace(
        broadcaster=SimpleNamespace(id="channel-1", name="channel"),
        chatter=SimpleNamespace(id="viewer-1", name="viewer"),
        reply=AsyncMock()
    )

    monkeypatch.setattr(points_commands, "get_context_broadcaster_id", lambda context: "channel-1")
    monkeypatch.setattr(points_commands, "get_active_profile", lambda broadcaster_id: SimpleNamespace(points=config))
    monkeypatch.setattr(points_commands, "is_feature_enabled", lambda bot, context, feature: True)
    monkeypatch.setattr(points_commands, "is_global_group_enabled", lambda bot, context, group: True)

    await PointsCommandHandler(bot).show_grouped_gamble_usage(ctx)

    assert events == ["reward"]
    ctx.reply.assert_awaited_once_with(
        "Gambling is grouped with this channel's loyalty commands. "
        "Use !petals gamble <amount> or !petals gamble all."
    )


@pytest.mark.asyncio
async def test_global_gamble_all_routes_to_guidance_without_placing_wager() -> None:
    component = PointsCommands(SimpleNamespace())
    component.handler.show_grouped_gamble_usage = AsyncMock()
    component.handler.gamble = AsyncMock()
    ctx = SimpleNamespace()

    await PointsCommands.gamble_usage.callback(component, ctx, attempted_amount="all")

    component.handler.show_grouped_gamble_usage.assert_awaited_once_with(ctx)
    component.handler.gamble.assert_not_awaited()
