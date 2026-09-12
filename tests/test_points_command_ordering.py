from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import bot.shared.commands.points as points_commands
from bot.shared.commands.points import PointsCommandHandler


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
        messages=SimpleNamespace(
            balance_self="{username}, you have {points} points.",
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
    ctx.reply.assert_awaited_once_with("viewer, you have 25 points.")
