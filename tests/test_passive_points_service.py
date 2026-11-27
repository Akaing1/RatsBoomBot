import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asqlite
import pytest
from twitchio.exceptions import HTTPException

import loyalty.passive as passive_module
from loyalty.passive import PassivePointsService


class FakeChatIdentity:
    def sender_id(self, broadcaster_id: str) -> str:
        return "bot-1"

    def is_custom_bot(self, user_id: str) -> bool:
        return user_id == "custom-bot"


class FakeFeatures:
    def is_enabled(self, broadcaster_id, feature) -> bool:
        return True


class FakeBroadcaster:

    def __init__(self, chatters):
        self.chatters = chatters
        self.fetch_chatter_calls = []

    async def fetch_chatters(self, **values):
        self.fetch_chatter_calls.append(values)
        return SimpleNamespace(users=self._iterate_chatters(), total=len(self.chatters))

    async def _iterate_chatters(self):
        for chatter in self.chatters:
            yield chatter


@pytest.mark.asyncio
async def test_missing_moderator_permission_pauses_passive_payout_retries(monkeypatch):
    clock = [1000.0]
    sleeps = 0

    async def sleep(_seconds):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 3:
            clock[0] += PassivePointsService.PERMISSION_RETRY_SECONDS
        if sleeps == 4:
            raise asyncio.CancelledError

    monkeypatch.setattr(passive_module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(passive_module.asyncio, "sleep", sleep)
    service = PassivePointsService(None, None, None, FakeChatIdentity(), None)
    service.award_interval = AsyncMock(side_effect=[
        HTTPException(status=403, extra={"message": "Not a moderator"}), 1
    ])

    with pytest.raises(asyncio.CancelledError):
        await service._run("channel-1", "stream-1")

    assert service.award_interval.await_count == 2
    assert "channel-1" not in service.permission_retry_at


@pytest.mark.asyncio
async def test_passive_points_awards_once_per_stream_interval(monkeypatch, tmp_path) -> None:
    chatters = [
        SimpleNamespace(id="viewer-1", name="viewer_one"),
        SimpleNamespace(id="channel-1", name="broadcaster"),
        SimpleNamespace(id="bot-1", name="main_bot"),
        SimpleNamespace(id="custom-bot", name="custom_bot")
    ]
    broadcaster = FakeBroadcaster(chatters)
    bot = SimpleNamespace(bot_id="bot-1", create_partialuser=lambda user_id: broadcaster)
    chatter_stats = SimpleNamespace(record_points_earned=AsyncMock())
    points = SimpleNamespace(chatter_stats=chatter_stats, pets=None)
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

        assert await service.award_interval("channel-1", "stream-1", interval_started_at=120) == 2
        assert await service.award_interval("channel-1", "stream-1", interval_started_at=120) == 0
        assert await service.award_interval("channel-1", "stream-1", interval_started_at=240) == 2

        async with database.acquire() as connection:
            row = await connection.fetchone(
                "SELECT points FROM viewers WHERE broadcaster_id = ? AND user_id = ?",
                ("channel-1", "viewer-1")
            )
            payouts = await connection.fetchone("SELECT COUNT(*) AS count FROM passive_point_payouts")

        assert int(row["points"]) == 30
        async with database.acquire() as connection:
            balances = await connection.fetchall("SELECT user_id, points FROM viewers ORDER BY user_id")

        assert {str(balance["user_id"]): int(balance["points"]) for balance in balances} == {"channel-1": 30, "viewer-1": 30}
        assert int(payouts["count"]) == 4
        assert chatter_stats.record_points_earned.await_count == 4
        assert sum(call.args[:3] == ("channel-1", "channel-1", 15) for call in chatter_stats.record_points_earned.await_args_list) == 2
        assert broadcaster.fetch_chatter_calls == [
            {"moderator": "bot-1", "first": 1000, "max_results": None},
            {"moderator": "bot-1", "first": 1000, "max_results": None},
            {"moderator": "bot-1", "first": 1000, "max_results": None}
        ]


@pytest.mark.asyncio
async def test_watch_xp_levels_only_equipped_pet_once_globally(monkeypatch, tmp_path):
    from loyalty.service import PointsService
    from pets import PetService
    from storage.migration_runner import run_migrations

    viewer = SimpleNamespace(id="viewer", name="viewer")
    bot = SimpleNamespace(bot_id="bot", create_partialuser=lambda _: FakeBroadcaster([viewer]))
    monkeypatch.setattr(passive_module, "get_active_profile", lambda _: object())
    async with asqlite.create_pool(str(tmp_path / "xp.db")) as database:
        await run_migrations(database)
        pets = PetService(database)
        points = PointsService(bot, database, pets=pets)
        service = PassivePointsService(bot, database, points, FakeChatIdentity(), FakeFeatures())
        await pets.grant_rat("viewer")
        bat = await pets.grant_bat("viewer")
        for tick in range(1, 11):
            await service.award_interval("one", "live", interval_started_at=120 * tick)
        leveled = await pets.get_equipped_pet("viewer")
        assert leveled.progress_label == "Level 2 · 0/120 XP"
        assert leveled.effective_passive_bps == bat.effective_passive_bps
        await pets.equip("viewer", "Little Rat")
        await service.award_interval("two", "other", interval_started_at=1200)
        assert (await pets.get_equipped_pet("viewer")).xp == 0
        await service.award_interval("two", "other", interval_started_at=1320)
        await service.award_interval("two", "other", interval_started_at=1320)
        assert (await pets.get_equipped_pet("viewer")).xp == 10
        await pets.equip("viewer", "Silly Bat")
        assert (await pets.get_equipped_pet("viewer")).level == 2
        async with database.acquire() as connection:
            await connection.execute("UPDATE user_pets SET level = 49, xp = 1055 WHERE id = ?", (bat.user_pet_id,))
        for tick in (12, 13):
            await service.award_interval("one", "live", interval_started_at=120 * tick)
        capped = await pets.get_equipped_pet("viewer")
        assert capped.progress_label == "Level 50 · Max level"
        assert capped.xp == 0
        assert capped.passive_percent == 7.5
