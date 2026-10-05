"""Release 13 keeps historical pet data dormant for release 14."""
import asqlite
import pytest

from bot.services.engagement.points import PointsService
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
@pytest.mark.parametrize('passive', ['loyalty_gain', 'gamble_loss_refund'])
async def test_existing_pet_data_is_preserved_without_reward_bonuses(tmp_path, passive):
    async with asqlite.create_pool(str(tmp_path / 'existing-uat.db')) as db:
        await run_migrations(db)
        async with db.acquire() as connection:
            await connection.execute(
                "INSERT INTO user_pets (user_id, pet_id, passive_type, passive_value_bps) VALUES ('viewer', 'dungeon_bat', ?, 1000)",
                (passive,),
            )
            await connection.execute("INSERT INTO user_pet_loadouts (user_id, user_pet_id) SELECT user_id, id FROM user_pets WHERE user_id = 'viewer'")
            await connection.execute("INSERT INTO pet_summon_tickets (user_id, broadcaster_id) VALUES ('viewer', 'channel')")
            await connection.commit()
            before = {table: [tuple(row) for row in await connection.fetchall(f'SELECT * FROM {table}')] for table in ('user_pets', 'user_pet_loadouts', 'pet_summon_tickets')}
        await run_migrations(db)
        points = PointsService(None, db)
        await points.setup()
        await points.add_points('channel', 'viewer', 'viewer', 100, earned=True)
        assert await points.get_points('channel', 'viewer') == 100
        assert await points.settle_wager('channel', 'viewer', 'viewer', bet=50, payout=0, game='gamble') == 50
        async with db.acquire() as connection:
            after = {table: [tuple(row) for row in await connection.fetchall(f'SELECT * FROM {table}')] for table in before}
        assert after == before
