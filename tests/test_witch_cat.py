import asqlite
import pytest

from pets.passives import GAMBLE_ODDS
from pets.service import PetService
from storage import migration_runner


@pytest.mark.asyncio
async def test_cat_upgrade_and_repeat_grant_preserve_existing_loadout(tmp_path, monkeypatch):
    migrations = migration_runner.MIGRATIONS
    async with asqlite.create_pool(str(tmp_path / 'cat.db')) as database:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 62))
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_poc_bat('viewer')
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await migration_runner.run_migrations(database)
        await migration_runner.run_migrations(database)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id

        cat = await pets.grant_pet('viewer', 'witch_cat', GAMBLE_ODDS)
        async with database.acquire() as connection:
            await connection.execute('UPDATE user_pets SET level = 5, xp = 42 WHERE id = ?', (cat.user_pet_id,))
            await connection.commit()
        repeated = await pets.grant_pet('viewer', 'witch_cat', GAMBLE_ODDS)
        assert repeated.user_pet_id == cat.user_pet_id
        assert (repeated.level, repeated.xp) == (5, 42)
        assert (repeated.display_name, repeated.rarity, repeated.sprite_path, repeated.frame_count) == (
            "Witch's Cat", 'common', '/assets/Witch%27s%20Cat.png', 4
        )
        assert repeated.passive_type == GAMBLE_ODDS
        assert cat.passive_percent == 5
        assert len(await pets.get_collection('viewer')) == 2
        await pets.grant_pet('viewer', 'explosive_rat', 'loyalty_gain')
        assert await pets.bonus_bps('viewer', GAMBLE_ODDS) == 0
        assert (await pets.equip('viewer', "Witch's Cat")).user_pet_id == cat.user_pet_id
