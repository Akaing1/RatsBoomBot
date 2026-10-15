import asqlite
import pytest

from bot.services.engagement.pets import LOYALTY_GAIN_PASSIVE, PetService
from bot.services.engagement.points import PointsService
from storage.migration_runner import run_migrations
from storage.migrations.v049_pet_asset_path import migrate as migrate_pet_asset_path


@pytest.mark.asyncio
async def test_poc_bat_is_global_and_buffs_earned_points_only(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as database:
        await run_migrations(database)
        pets = PetService(database)
        points = PointsService(bot=None, db=database, pets=pets)
        pet = await pets.grant_pet("viewer-1", "dungeon_bat", LOYALTY_GAIN_PASSIVE)

        assert pet.pet_id == "dungeon_bat"
        assert pet.passive_type == LOYALTY_GAIN_PASSIVE
        assert pet.passive_percent == 10

        await points.add_points("channel-1", "viewer-1", "viewer", 100)
        await points.add_points("channel-2", "viewer-1", "viewer", 50)
        await points.add_points("channel-1", "viewer-1", "viewer", 20, earned=False)

        assert await points.get_points("channel-1", "viewer-1") == 130
        assert await points.get_points("channel-2", "viewer-1") == 55


@pytest.mark.asyncio
async def test_granting_poc_bat_twice_keeps_one_global_pet_and_loadout(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as database:
        await run_migrations(database)
        pets = PetService(database)

        first = await pets.grant_poc_bat("viewer-1")
        second = await pets.grant_poc_bat("viewer-1")

        async with database.acquire() as connection:
            owned = await connection.fetchone(
                "SELECT COUNT(*) AS count FROM user_pets WHERE user_id = ?",
                ("viewer-1",)
            )
            equipped = await connection.fetchone(
                "SELECT COUNT(*) AS count FROM user_pet_loadouts WHERE user_id = ?",
                ("viewer-1",)
            )

        assert first.user_pet_id == second.user_pet_id
        assert int(owned["count"]) == 1
        assert int(equipped["count"]) == 1


@pytest.mark.asyncio
async def test_transfers_and_gambling_payouts_do_not_receive_pet_bonus(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as database:
        await run_migrations(database)
        pets = PetService(database)
        points = PointsService(bot=None, db=database, pets=pets)
        await pets.grant_pet("viewer-1", "dungeon_bat", LOYALTY_GAIN_PASSIVE)

        await points.add_points("channel-1", "viewer-1", "viewer", 100, earned=False)
        await points.add_points("channel-1", "sender-1", "sender", 50, earned=False)
        await points.transfer_points("channel-1", "sender-1", "viewer-1", "viewer", 20)
        balance = await points.settle_wager(
            "channel-1",
            "viewer-1",
            "viewer",
            bet=10,
            payout=20
        )

        assert balance == 130


@pytest.mark.asyncio
async def test_pet_asset_migration_updates_existing_bat_path(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as database:
        await run_migrations(database)

        async with database.acquire() as connection:
            await connection.execute(
                "UPDATE pet_definitions SET sprite_path = ? WHERE id = ?",
                ("/static/img/dungeon-bat.png", "dungeon_bat")
            )
            await migrate_pet_asset_path(connection)
            row = await connection.fetchone(
                "SELECT sprite_path FROM pet_definitions WHERE id = ?",
                ("dungeon_bat",)
            )

        assert row["sprite_path"] == "/assets/bat.png"


@pytest.mark.asyncio
async def test_sleepy_fox_grant_preserves_ownership_and_equips(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / 'fox.db')) as database:
        await run_migrations(database)
        pets = PetService(database)
        first = await pets.grant_fox('viewer')
        second = await pets.grant_fox('viewer')
        assert first.user_pet_id == second.user_pet_id
        assert (second.pet_id, second.display_name, second.rarity, second.sprite_path, second.frame_count) == (
            'sleepy_fox', 'Sleepy Fox', 'common', '/assets/Sleepy%20Fox.png', 4
        )
        assert (await pets.get_equipped_pet('viewer')).pet_id == 'sleepy_fox'


@pytest.mark.asyncio
async def test_horned_wolf_upgrade_and_repeat_grant_preserve_existing_pets(tmp_path, monkeypatch):
    from storage import migration_runner
    from pets.passives import RAID_DAMAGE
    migrations = migration_runner.MIGRATIONS
    async with asqlite.create_pool(str(tmp_path / 'wolf.db')) as database:
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', tuple(m for m in migrations if m.version < 59))
        await run_migrations(database)
        pets = PetService(database)
        bat = await pets.grant_poc_bat('viewer')
        monkeypatch.setattr(migration_runner, 'MIGRATIONS', migrations)
        await run_migrations(database)
        await run_migrations(database)
        assert (await pets.get_equipped_pet('viewer')).user_pet_id == bat.user_pet_id
        first = await pets.grant_pet('viewer', 'horned_wolf', RAID_DAMAGE)
        second = await pets.grant_pet('viewer', 'horned_wolf', RAID_DAMAGE)
        assert first.user_pet_id == second.user_pet_id
        assert (second.display_name, second.rarity, second.sprite_path, second.frame_count) == (
            'Horned Wolf', 'common', '/assets/Horned%20Wolf.png', 4
        )
        assert await pets.bonus_bps('viewer', RAID_DAMAGE) == 1000
        assert len(await pets.get_collection('viewer')) == 2
        assert (await pets.equip('viewer', 'Horned Wolf')).user_pet_id == first.user_pet_id
