import asqlite
import pytest

from bot.services.engagement.pets import LOYALTY_GAIN_PASSIVE, PetService
from bot.services.engagement.points import PointsService
from storage.migration_runner import run_migrations


@pytest.mark.asyncio
async def test_poc_bat_is_global_and_buffs_earned_points_only(tmp_path) -> None:
    async with asqlite.create_pool(str(tmp_path / "pets.db")) as database:
        await run_migrations(database)
        pets = PetService(database)
        points = PointsService(bot=None, db=database, pets=pets)
        pet = await pets.grant_poc_bat("viewer-1")

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
        await pets.grant_poc_bat("viewer-1")

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

