import asqlite
import pytest

from bot.services.channels.achievements import AchievementService
from bot.services.engagement.points import PointsService
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_secret_loss_threshold_global_totals_and_no_leak(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'gambling.db')) as db:
        await run_migrations(db)
        points = PointsService(None, db)
        await points.setup()
        achievements = AchievementService(db)
        async def collection():
            return await achievements.get_collection('u', lambda channel: {})
        before = await collection()
        assert before['available'] == 40
        assert 'The House Always Wins' not in str(before)
        for channel in ('a', 'b'):
            await points.add_points(channel, 'u', 'viewer', 600000, earned=False)
        await points.settle_wager('a', 'u', 'viewer', 250000, 0)
        await points.settle_wager('b', 'u', 'viewer', 249999, 0)
        assert 'The House Always Wins' not in str(await collection())
        assert await points.settle_wager('b', 'u', 'viewer', 9999999, 0) is None
        await points.settle_wager('b', 'u', 'viewer', 1, 0)
        card = next(c for c in (await collection())['cards'] if c['standalone'])
        assert card['tier'] == 'Platinum'
        assert len(card['steps']) == 1
        assert card['progress'] == 500000
        assert (await collection())['available'] == 41
        await points.settle_wager('a', 'u', 'renamed', 5000, 10000)
        cards = (await collection())['cards']
        assert next(c for c in cards if c['title'] == 'Lucky Break')['progress'] == 5000
        assert next(c for c in cards if c['standalone'])['progress'] == 500000
        async with db.acquire() as c:
            assert len(await c.fetchall("SELECT * FROM achievement_unlocks WHERE achievement_id='house'")) == 1
        assert 'The House Always Wins' not in str(await achievements.get_collection('other', lambda channel: {}))


@pytest.mark.asyncio
async def test_earnings_and_unlocks_rollback_together(tmp_path):
    async with asqlite.create_pool(str(tmp_path / 'rollback.db')) as db:
        await run_migrations(db)
        async with db.acquire() as c:
            await c.execute('BEGIN')
            await c.execute("INSERT INTO chatter_channel_stats (broadcaster_id,user_id,lifetime_points_earned) VALUES ('a','u',10000)")
            assert await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='collector'")
            await c.rollback()
            assert not await c.fetchone("SELECT 1 FROM achievement_unlocks WHERE achievement_id='collector'")
