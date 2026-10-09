import asqlite
import pytest

from pets import PetService
from storage import migration_runner


@pytest.mark.asyncio
@pytest.mark.parametrize("already_owned", [False, True])
async def test_previous_rat_seed_is_repaired_without_losing_equipment(tmp_path, monkeypatch, already_owned):
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as db:
        migrations = migration_runner.MIGRATIONS
        monkeypatch.setattr(migration_runner, "MIGRATIONS", tuple(m for m in migrations if m.version < 53))
        await migration_runner.run_migrations(db)
        pets = PetService(db)
        old_pet = await pets.grant_rat("viewer") if already_owned else None

        async with db.acquire() as connection:
            await connection.execute(
                "INSERT INTO pet_definitions (id, display_name, rarity, sprite_path, frame_count, max_level) "
                "VALUES ('dungeon_rat', 'Dungeon Rat', 'common', '/assets/rat.png', 4, 50)"
            )
            if already_owned:
                await connection.execute("UPDATE user_pets SET pet_id = 'dungeon_rat' WHERE user_id = 'viewer'")
            await connection.execute("DELETE FROM pet_definitions WHERE id = 'explosive_rat'")

        monkeypatch.setattr(migration_runner, "MIGRATIONS", migrations)
        await migration_runner.run_migrations(db)
        rat = await pets.grant_rat("viewer")
        assert (rat.pet_id, rat.display_name, rat.sprite_path) == (
            "explosive_rat", "Little Rat", "/assets/Explosive%20Rat.png"
        )
        if old_pet is not None:
            assert rat.user_pet_id == old_pet.user_pet_id
        async with db.acquire() as connection:
            assert await connection.fetchone("SELECT id FROM pet_definitions WHERE id = 'dungeon_rat'") is None
