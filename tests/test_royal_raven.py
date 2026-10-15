import asqlite
import pytest

from pets.passives import RAID_PROFIT
from pets.service import PetService
from storage import migration_runner


@pytest.mark.asyncio
async def test_raven_upgrade_and_repeat_grant_preserve_existing_loadout(tmp_path, monkeypatch):
    migrations = migration_runner.MIGRATIONS
    async with asqlite.create_pool(str(tmp_path / 'raven.db')) as database:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 60))
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_poc_bat('viewer')
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await migration_runner.run_migrations(database)
        await migration_runner.run_migrations(database)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id

        raven = await pets.grant_pet('viewer', 'royal_raven', RAID_PROFIT)
        async with database.acquire() as connection:
            await connection.execute('UPDATE user_pets SET level = 5, xp = 42 WHERE id = ?', (raven.user_pet_id,))
            await connection.commit()
        repeated = await pets.grant_pet('viewer', 'royal_raven', RAID_PROFIT)
        assert repeated.user_pet_id == raven.user_pet_id
        assert (repeated.level, repeated.xp) == (5, 42)
        assert (repeated.display_name, repeated.rarity, repeated.sprite_path, repeated.frame_count) == (
            'Royal Raven', 'common', '/assets/Royal%20Raven.png', 4
        )
        assert repeated.passive_type == RAID_PROFIT
        assert raven.passive_percent == 10
        assert len(await pets.get_collection('viewer')) == 2
        await pets.equip('viewer', 'Silly Bat')
        assert await pets.bonus_bps('viewer', RAID_PROFIT) == 0
        assert (await pets.equip('viewer', 'Royal Raven')).user_pet_id == raven.user_pet_id
