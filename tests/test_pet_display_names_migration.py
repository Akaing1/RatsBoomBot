import asqlite
import pytest
from fastapi.testclient import TestClient

from pets import PetService
from storage import migration_runner
from web.app import app


@pytest.mark.asyncio
async def test_existing_equipped_pets_keep_ownership_after_rename(tmp_path, monkeypatch):
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as database:
        migrations = migration_runner.MIGRATIONS
        monkeypatch.setattr(migration_runner, "MIGRATIONS", tuple(m for m in migrations if m.version < 54))
        await migration_runner.run_migrations(database)
        pets = PetService(database)
        bat_before = await pets.grant_poc_bat("bat-owner")
        rat_before = await pets.grant_rat("rat-owner")

        monkeypatch.setattr(migration_runner, "MIGRATIONS", migrations)
        await migration_runner.run_migrations(database)
        bat_after = await pets.get_equipped_pet("bat-owner")
        rat_after = await pets.get_equipped_pet("rat-owner")

        assert (bat_after.user_pet_id, bat_after.pet_id, bat_after.display_name, bat_after.sprite_path) == (
            bat_before.user_pet_id, "dungeon_bat", "Silly Bat", "/assets/Silly%20Bat.png"
        )
        assert bat_after.rarity == rat_after.rarity == "common"
        assert rat_after.passive_type == rat_before.passive_type
        assert (rat_after.user_pet_id, rat_after.pet_id, rat_after.display_name, rat_after.sprite_path) == (
            rat_before.user_pet_id, "explosive_rat", "Little Rat", "/assets/Explosive%20Rat.png"
        )


def test_named_sprite_urls_are_served():
    with TestClient(app) as client:
        for name in ("Silly%20Bat", "Explosive%20Rat", "Sleepy%20Fox"):
            response = client.get(f"/assets/{name}.png")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/png"
