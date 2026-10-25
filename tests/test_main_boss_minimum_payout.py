import asqlite
import pytest
from tests.test_raid_boss_service import build_config
from loyalty.service import PointsService
from bot.services.engagement.raid_boss import RaidBossService
from storage.migration_runner import run_migrations

@pytest.mark.asyncio
@pytest.mark.parametrize("tier,damage,expected", [
    ("main", 100, 1500),
    ("main", 1500, 2250),
    ("main", 2499, 3748),
    ("main", 2500, 3750),
    ("main", 0, 0),
    ("mini", 100, 150),
])
async def test_main_boss_low_damage_minimum_pool(tmp_path, tier, damage, expected):
    async with asqlite.create_pool(str(tmp_path / "minimum.db")) as database:
        points = PointsService(bot=None, db=database)
        service = RaidBossService(bot=None, db=database)
        await points.setup()
        await run_migrations(database)
        await service.setup()
        config = build_config(critical_chance=0, max_hp=10000, base_damage_min=damage, base_damage_max=damage)
        event = await service.spawn("channel-1", "melee", config, tier)
        if damage:
            await service.attack("channel-1", "stream-1", "user-1", "alice", config)
        assert await service.resolve("channel-1", defeated=False) == expected
        assert await points.get_points("channel-1", "user-1") == expected
        # Resolution cannot pay twice.
        assert await service.resolve("channel-1", defeated=False) == 0
