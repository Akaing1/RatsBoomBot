from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest

import bot.services.engagement.passive_points as passive_module
from bot.services.engagement.passive_points import PassivePointsService


class FakeChatIdentity:
    def sender_id(self, broadcaster_id: str) -> str:
        return "bot-1"

    def is_custom_bot(self, user_id: str) -> bool:
        return user_id == "custom-bot"


class FakeFeatures:
    def is_enabled(self, broadcaster_id, feature) -> bool:
        return True


@pytest.mark.asyncio
async def test_passive_points_awards_once_per_stream_interval(monkeypatch, tmp_path) -> None:
    chatters = SimpleNamespace(users=[
        SimpleNamespace(id="viewer-1", name="viewer_one"),
        SimpleNamespace(id="channel-1", name="broadcaster"),
        SimpleNamespace(id="bot-1", name="main_bot"),
        SimpleNamespace(id="custom-bot", name="custom_bot")
    ])
    broadcaster = SimpleNamespace(fetch_chatters=AsyncMock(return_value=chatters))
    bot = SimpleNamespace(bot_id="bot-1", create_partialuser=lambda user_id: broadcaster)
    chatter_stats = SimpleNamespace(record_points_earned=AsyncMock())
    points = SimpleNamespace(chatter_stats=chatter_stats)
    monkeypatch.setattr(passive_module, "get_active_profile", lambda broadcaster_id: object())

    async with asqlite.create_pool(str(tmp_path / "passive.db")) as database:
        async with database.acquire() as connection:
            await connection.execute(
                """
                CREATE TABLE viewers (
                    broadcaster_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0,
                    messages INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (broadcaster_id, user_id)
                )
                """
            )

        service = PassivePointsService(bot, database, points, FakeChatIdentity(), FakeFeatures())
        await service.setup()

        assert await service.award_interval("channel-1", "stream-1", interval_started_at=120) == 1
        assert await service.award_interval("channel-1", "stream-1", interval_started_at=120) == 0
        assert await service.award_interval("channel-1", "stream-1", interval_started_at=240) == 1

        async with database.acquire() as connection:
            row = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id = ? AND user_id = ?",
                ("channel-1", "viewer-1")
            )
            payouts = await connection.fetchone("SELECT COUNT(*) AS count FROM passive_point_payouts")

        assert int(row["points"]) == 20
        assert int(payouts["count"]) == 2
        assert chatter_stats.record_points_earned.await_count == 2
        broadcaster.fetch_chatters.assert_awaited_with(
            moderator="bot-1",
            first=1000,
            max_results=None,
            token_for="bot-1"
        )
