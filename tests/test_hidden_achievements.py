import asyncio

import asqlite
import pytest

from bot.profiles import RaidBossConfig
from bot.services.channels.achievements import AchievementService
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService
from storage.migrations import MIGRATIONS
from storage.migration_runner import run_migrations
from storage.migrations.v032_global_blessed_achievements import BLESSINGS


@pytest.mark.asyncio
async def test_existing_blessed_collection_merges_and_unlocks(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'old.db')) as db:
        async with db.acquire() as c:
            for migration in MIGRATIONS[:31]:
                await migration.run(c)
            for index, weapon in enumerate(BLESSINGS):
                await c.execute('INSERT INTO raid_boss_inventory VALUES (?,?,?,1,12)', (str(index), 'u', weapon))
            await c.execute('INSERT INTO raid_boss_inventory VALUES (?,?,?,1,30)', ('another', 'u', BLESSINGS[0]))
            await MIGRATIONS[31].run(c)
            rows = await c.fetchall("SELECT * FROM raid_boss_inventory WHERE user_id='u'")
            assert len(rows) == 5
            assert all(row['broadcaster_id'] == '' and row['quantity'] == 1 for row in rows)
            assert max(row['durability'] for row in rows) == 30
            unlock = await c.fetchone("SELECT * FROM achievement_unlocks WHERE achievement_id='stones'")
            assert unlock['tier'] == 4 and unlock['unlocked_at'] is None


@pytest.mark.asyncio
async def test_hidden_unlocks_require_distinct_weapons_and_100_successes(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'new.db')) as db:
        await run_migrations(db)
        service = AchievementService(db)
        for index in range(99):
            await service.record_kamikaze_success(str(index % 2), str(index), 'u', 'target')
        await service.record_kamikaze_success('0', '0', 'u', 'target')
        await service.record_kamikaze_success('0', 'self', 'u', 'u')
        async with db.acquire() as c:
            for weapon in BLESSINGS[:4]:
                await c.execute('INSERT INTO raid_boss_inventory VALUES (?,?,?,1,35)', ('', 'u', weapon))
            await c.execute("UPDATE raid_boss_inventory SET quantity=2 WHERE item_id=?", (BLESSINGS[0],))
        collection = await service.get_collection('u', lambda _: {})
        assert not any(card['title'] in {'Collecting the Stones', 'Rat Exterminator'} for card in collection['cards'])
        await service.record_kamikaze_success('b', '100', 'u', 'target')
        async with db.acquire() as c:
            await c.execute('INSERT INTO raid_boss_inventory VALUES (?,?,?,1,35)', ('', 'u', BLESSINGS[4]))
        collection = await service.get_collection('u', lambda _: {})
        hidden = [card for card in collection['cards'] if card['title'] in {'Collecting the Stones', 'Rat Exterminator'}]
        assert len(hidden) == 2
        assert all(card['tier'] == 'Platinum' and card['standalone'] and len(card['steps']) == 1 for card in hidden)


@pytest.mark.asyncio
async def test_blessed_weapon_cross_channel_durability_and_repair(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / 'global.db')) as db:
        await run_migrations(db)
        raid = RaidBossService(None, db)
        points = PointsService(None, db)
        config = RaidBossConfig(base_damage_min=100, base_damage_max=100)
        monkeypatch.setattr('bot.services.engagement.raid_boss.random.random', lambda: 1.0)
        async with db.acquire() as c:
            await c.execute('INSERT INTO raid_boss_inventory VALUES (?,?,?,1,1)', ('', 'u', BLESSINGS[0]))
            await c.execute('INSERT INTO raid_boss_inventory VALUES (?,?,?,1,15)', ('a', 'u', 'basic_sword'))
        for channel in ('a', 'b'):
            await raid.spawn(channel, 'melee', config)
            assert await raid.equip(channel, 'u', 'viewer', BLESSINGS[0])
        assert not await raid.equip('b', 'u', 'viewer', 'basic_sword')
        attacks = await asyncio.gather(*(raid.attack(channel, 's', 'u', 'viewer', config) for channel in ('a','b')))
        assert sum(bool(attack.weapon_passive) for attack in attacks) == 1
        assert (await raid.get_inventory('b', 'u'))[2] == 0
        await points.add_points('b', 'u', 'viewer', 5000)
        assert await raid.repair('b', 'u', BLESSINGS[0], config) == 'repaired'
        assert await points.get_points('b', 'u') == 0
        assert (await raid.get_inventory('a', 'u'))[2] == 35
