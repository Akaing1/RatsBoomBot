import sqlite3

import asqlite
import pytest

from bot.profiles import RaidBossConfig
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService
from storage.migration_runner import run_migrations
from storage.migrations import MIGRATIONS


@pytest.mark.asyncio
async def test_purchases_count_only_success_and_rollback_with_balance(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'raid.db')) as db:
        await run_migrations(db)
        points = PointsService(None, db)
        raid = RaidBossService(None, db)
        config = RaidBossConfig()
        await points.add_points('a', 'u', 'viewer', 1000000)
        assert await raid.buy('a', 'u', 'viewer', 'sword', config) == 'purchased'
        assert await raid.buy('a', 'u', 'viewer', 'potion', config, 's') == 'purchased'
        assert await raid.buy('a', 'u', 'viewer', 'blessing', config, 's') == 'purchased'
        assert (await raid.buy('a', 'u', 'viewer', 'blessing', config, 's')).startswith('out_of_stock')
        assert await raid.buy('a', 'poor', 'poor', 'sword', config) == 'insufficient'
        async with db.acquire() as c:
            rows = await c.fetchall('SELECT category, purchases FROM raid_purchase_totals')
            assert {r['category']: r['purchases'] for r in rows} == {'weapons': 1, 'consumables': 1, 'buffs': 1}
            await c.execute("CREATE TRIGGER fail_purchase BEFORE UPDATE ON raid_purchase_totals BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        before = await points.get_points('a', 'u')
        with pytest.raises(sqlite3.IntegrityError):
            await raid.buy('a', 'u', 'viewer', 'sword', config)
        assert await points.get_points('a', 'u') == before
        async with db.acquire() as c:
            row = await c.fetchone("SELECT SUM(quantity) AS quantity FROM raid_boss_inventory WHERE user_id='u'")
            assert row['quantity'] == 1


@pytest.mark.asyncio
async def test_damage_backfill_and_bonus_contribution_unlock(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'damage.db')) as db:
        async with db.acquire() as c:
            for migration in MIGRATIONS[:30]:
                await migration.run(c)
            await c.execute("INSERT INTO raid_boss_attacks (event_id,broadcaster_id,stream_id,user_id,username,damage,attacked_at) VALUES (1,'a','s','u','viewer',10000,'2026-09-01')")
            await MIGRATIONS[30].run(c)
            row = await c.fetchone("SELECT * FROM achievement_unlocks WHERE achievement_id='damage'")
            assert row['tier'] == 1 and row['unlocked_at'] is None
            await c.execute("INSERT INTO raid_boss_bonus_contributions VALUES (2,'s','attacker',1,'b','u','viewer',90000)")
            rows = await c.fetchall("SELECT * FROM achievement_unlocks WHERE achievement_id='damage' ORDER BY tier")
            assert len(rows) == 2 and rows[1]['unlocked_at'] is not None
            assert not await c.fetchone('SELECT 1 FROM raid_purchase_totals')
