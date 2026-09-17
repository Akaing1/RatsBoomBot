import asqlite
import pytest

from bot.services.channels.chatter_levels import ChatterLevelService
from storage.migration_runner import run_migrations


def test_quadratic_level_boundaries() -> None:
    assert ChatterLevelService.calculate(0, 0) == {
        "level": 1, "total_xp": 0, "achievement_xp": 0, "raid_xp": 0,
        "current_xp": 0, "xp_required": 500, "next_level_at": 500, "percent": 0
    }
    assert ChatterLevelService.calculate(499, 0)["level"] == 1
    assert ChatterLevelService.calculate(500, 0)["level"] == 2
    assert ChatterLevelService.calculate(1999, 0)["level"] == 2
    assert ChatterLevelService.calculate(2000, 0)["level"] == 3


@pytest.mark.asyncio
async def test_global_level_combines_achievement_tiers_and_contributed_raid_clears(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "levels.db")) as database:
        await run_migrations(database)

        async with database.acquire() as connection:
            await connection.execute("INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier) VALUES ('user-1','','explorer',1)")
            await connection.execute("INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier) VALUES ('user-1','','regular',2)")
            await connection.execute("INSERT INTO achievement_unlocks (user_id,broadcaster_id,achievement_id,tier) VALUES ('user-1','','house',4)")
            await connection.execute("INSERT INTO raid_boss_events (id,broadcaster_id,boss_name,boss_type,boss_tier,max_hp,current_hp,reward_pool,final_hit_reward,status,spawned_at,stream_limit) VALUES (1,'channel-1','Boss','melee','main',1000,0,1000,100,'defeated','2026-09-17',3)")
            await connection.execute("INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (1,'channel-1','stream-1','user-1','alice',100,'2026-09-17')")

        level = await ChatterLevelService(database).get_global_level("user-1")

        assert level == {
            "level": 2,
            "total_xp": 1450,
            "achievement_xp": 1350,
            "raid_xp": 100,
            "current_xp": 950,
            "xp_required": 1500,
            "next_level_at": 2000,
            "percent": 63
        }
