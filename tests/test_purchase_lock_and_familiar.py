import asyncio

import asqlite
import pytest

from bot.profiles import RaidBossConfig
from bot.services.engagement.points import PointsService
from bot.services.engagement.raid_boss import RaidBossService
from bot.services.channels.achievements import AchievementService
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_parallel_purchases(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'parallel.db'), size=3) as db:
        await run_migrations(db)
        points = PointsService(None, db)
        raid = RaidBossService(None, db)
        await points.add_points('a', 'u', 'viewer', 2000)
        results = await asyncio.gather(*(raid.buy('a', 'u', 'viewer', 'sword', RaidBossConfig(weapon_cost=1000)) for _ in range(3)))
        assert results.count('purchased') == 2
        assert results.count('insufficient') == 1
        assert await points.get_points('a', 'u') == 500
        async with db.acquire() as c:
            row = await c.fetchone("SELECT purchases FROM raid_purchase_totals WHERE user_id='u'")
            assert row['purchases'] == 2


@pytest.mark.asyncio
async def test_familiar_global_max_and_unique_tiers(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'familiar.db')) as db:
        await run_migrations(db)
        async with db.acquire() as c:
            for channel, count in [('a', 40), ('b', 30)]:
                await c.execute("INSERT INTO imported_redeem_totals (broadcaster_id,user_id,username,redeem_type,claim_count) VALUES (?,'u','viewer','daily',?)", (channel, count))
        service = AchievementService(db)
        result = await service.get_collection('u', lambda channel: {})
        cards = [card for card in result['cards'] if card['title'] == 'Familiar Face']
        assert len(cards) == 1 and cards[0]['scope'] == 'global'
        assert cards[0]['progress'] == 40 and cards[0]['tier'] == 'Bronze'
        async with db.acquire() as c:
            await c.execute("UPDATE imported_redeem_totals SET claim_count=50 WHERE broadcaster_id='b'")
        result = await service.get_collection('u', lambda channel: {})
        card = next(card for card in result['cards'] if card['title'] == 'Familiar Face')
        assert card['progress'] == 50 and card['tier'] == 'Silver'
