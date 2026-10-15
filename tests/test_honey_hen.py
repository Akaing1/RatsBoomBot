import asqlite
import pytest

from pets.passives import LOYALTY_GAIN
from pets.service import PetService
from storage import migration_runner


@pytest.mark.asyncio
async def test_honey_hen_upgrade_and_repeat_grant_preserve_existing_loadout(tmp_path, monkeypatch):
    migrations = migration_runner.MIGRATIONS
    async with asqlite.create_pool(str(tmp_path / 'honey-hen.db')) as database:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 64))
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_poc_bat('viewer')
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await migration_runner.run_migrations(database)
        await migration_runner.run_migrations(database)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id

        hen = await pets.grant_pet('viewer', 'honey_hen', LOYALTY_GAIN)
        async with database.acquire() as connection:
            await connection.execute('UPDATE user_pets SET level = 5, xp = 42 WHERE id = ?', (hen.user_pet_id,))
            await connection.commit()
        repeated = await pets.grant_pet('viewer', 'honey_hen', LOYALTY_GAIN)
        assert repeated.user_pet_id == hen.user_pet_id
        assert (repeated.level, repeated.xp) == (5, 42)
        assert (repeated.display_name, repeated.rarity, repeated.sprite_path, repeated.frame_count) == (
            "Honey Hen", 'common', '/assets/Honey%20Hen.png', 4
        )
        assert repeated.passive_type == LOYALTY_GAIN
        assert hen.passive_percent == 10
        assert len(await pets.get_collection('viewer')) == 2
        await pets.grant_pet('viewer', 'royal_raven', 'raid_profit')
        assert await pets.bonus_bps('viewer', LOYALTY_GAIN) == 0
        assert (await pets.equip('viewer', "Honey Hen")).user_pet_id == hen.user_pet_id
