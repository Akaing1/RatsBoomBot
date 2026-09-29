import argparse
import asyncio
from pathlib import Path

import asqlite

from pets import PetService
from pets.passives import PASSIVES, RAID_DAMAGE
from config.settings import settings
from storage.migration_runner import run_migrations


async def grant_pet(chatter: str, pet_id: str = "bat", passive_type: str = RAID_DAMAGE) -> None:
    database_path = Path(settings.DATABASE_PATH)
    normalized = chatter.strip().removeprefix("@").strip()

    async with asqlite.create_pool(str(database_path)) as database:
        await run_migrations(database)

        async with database.acquire() as connection:
            identity = await connection.fetchone(
                """
                SELECT user_id, display_name
                FROM chatter_identities
                WHERE user_id = ? OR login = ? COLLATE NOCASE OR display_name = ? COLLATE NOCASE
                LIMIT 1
                """,
                (normalized, normalized, normalized)
            )

        if identity is None:
            raise SystemExit(f"No chatter identity found for '{chatter}'.")

        service = PetService(database)
        pet = await (service.grant_poc_bat(str(identity["user_id"])) if pet_id == "bat" else service.grant_rat(str(identity["user_id"]), passive_type))
        print(
            f"Equipped {pet.display_name} for {identity['display_name']} "
            f"({pet.rarity}) with {pet.passive_name} ({pet.passive_rarity}): "
            f"{pet.passive_percent:g}% {pet.passive_description}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant and equip a test pet on the selected environment.")
    parser.add_argument("chatter", help="Twitch login, display name, or user ID")
    parser.add_argument("--pet", choices=("bat", "rat"), default="bat")
    parser.add_argument("--passive", choices=tuple(PASSIVES), default=RAID_DAMAGE, help="Rat passive (bat keeps its loyalty bonus)")
    arguments = parser.parse_args()
    asyncio.run(grant_pet(arguments.chatter, arguments.pet, arguments.passive))


if __name__ == "__main__":
    main()
