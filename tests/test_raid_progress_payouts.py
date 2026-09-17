from unittest.mock import AsyncMock

import asqlite
import pytest

from bot.profiles import RaidBossConfig
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService
from storage.migration_runner import run_migrations


def config(**overrides):
    values = {"enabled": True, "max_hp": 1000, "base_damage_min": 100, "base_damage_max": 100}
    values.update(overrides)
    return RaidBossConfig(**values)


@pytest.mark.asyncio
async def test_checkpoints_announce_once_and_persist_across_restart(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 1.0)
    path = str(tmp_path / "checkpoints.db")

    async with asqlite.create_pool(path) as database:
        await run_migrations(database)
        service = RaidBossService(bot=None, db=database)
        service.send_announcement = AsyncMock()
        raid_config = config(base_damage_min=250, base_damage_max=250)
        await service.spawn("channel", "melee", raid_config)

        for stream in ("one", "two", "three"):
            await service.attack("channel", stream, "user", "viewer", raid_config)

        messages = [call.args[1] for call in service.send_announcement.await_args_list]
        assert len(messages) == 3
        assert "75% HP remains" in messages[0]
        assert "50% HP" in messages[1]
        assert "Only 25% HP remains" in messages[2]

    async with asqlite.create_pool(path) as database:
        restarted = RaidBossService(bot=None, db=database)
        restarted.send_announcement = AsyncMock()
        await restarted.attack("channel", "four", "user", "viewer", raid_config)
        restarted.send_announcement.assert_not_awaited()
        async with database.acquire() as connection:
            rows = await connection.fetchall("SELECT checkpoint FROM raid_boss_health_checkpoints ORDER BY checkpoint")
        assert [row["checkpoint"] for row in rows] == [25, 50, 75]


@pytest.mark.asyncio
async def test_large_attack_announces_highest_new_checkpoint_without_stacking_messages(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 1.0)
    async with asqlite.create_pool(str(tmp_path / "jump.db")) as database:
        await run_migrations(database)
        service = RaidBossService(bot=None, db=database)
        service.send_announcement = AsyncMock()
        raid_config = config(base_damage_min=600, base_damage_max=600)
        await service.spawn("channel", "melee", raid_config)
        await service.attack("channel", "one", "user", "viewer", raid_config)
        service.send_announcement.assert_awaited_once()
        assert "50% HP" in service.send_announcement.await_args.args[1]
        async with database.acquire() as connection:
            rows = await connection.fetchall("SELECT checkpoint FROM raid_boss_health_checkpoints ORDER BY checkpoint")
        assert [row["checkpoint"] for row in rows] == [25, 50]


@pytest.mark.asyncio
@pytest.mark.parametrize("boss_tier", ("mini", "tutorial"))
async def test_health_checkpoints_only_apply_to_main_bosses(tmp_path, monkeypatch, boss_tier):
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 1.0)
    async with asqlite.create_pool(str(tmp_path / f"{boss_tier}.db")) as database:
        await run_migrations(database)
        service = RaidBossService(bot=None, db=database)
        service.send_announcement = AsyncMock()
        raid_config = config(base_damage_min=250, base_damage_max=250)
        await service.spawn("channel", "melee", raid_config, boss_tier)
        await service.attack("channel", "one", "user", "viewer", raid_config)

        service.send_announcement.assert_not_awaited()
        async with database.acquire() as connection:
            rows = await connection.fetchall("SELECT checkpoint FROM raid_boss_health_checkpoints")
        assert rows == []


@pytest.mark.asyncio
async def test_partial_damage_uses_same_ranked_distribution_as_a_clear(tmp_path, monkeypatch):
    monkeypatch.setattr("bot.services.engagement.raid_boss.random.random", lambda: 1.0)
    async with asqlite.create_pool(str(tmp_path / "payout.db")) as database:
        await run_migrations(database)
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        raid_config = config()
        await service.spawn("channel", "melee", raid_config)
        await service.attack("channel", "one", "first", "first", raid_config)
        await service.attack("channel", "one", "second", "second", raid_config)
        total = await service.resolve("channel", defeated=False)

        assert total == 250
        assert await points.get_points("channel", "first") == 150
        assert await points.get_points("channel", "second") == 100


@pytest.mark.asyncio
async def test_zero_damage_conclusion_reports_and_pays_zero(tmp_path):
    async with asqlite.create_pool(str(tmp_path / "zero.db")) as database:
        await run_migrations(database)
        service = RaidBossService(bot=None, db=database)
        await service.spawn("channel", "melee", config())
        assert await service.resolve("channel", defeated=False) == 0
